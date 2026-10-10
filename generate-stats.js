// PRODUCTION INTEGRATION SCRIPT: scripts/generate-stats.js
const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth')();
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const winston = require('winston');
require('dotenv').config();

chromium.use(stealth);

const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.printf(({ timestamp, level, message }) => `[${timestamp}] ${level.toUpperCase()}: ${message}`)
    ),
    transports: [new winston.transports.Console()]
});

class ProductionScraper {
    static parseNumber(text) {
        if (!text) return 0;
        const clean = text.toString().toUpperCase().replace(/,/g, '').trim();
        let mult = 1;
        if (clean.includes('K')) mult = 1000;
        if (clean.includes('M')) mult = 1000000;
        if (clean.includes('B')) mult = 1000000000;
        const num = parseFloat(clean.replace(/[KMB]/g, ''));
        return isNaN(num) ? 0 : Math.floor(num * mult);
    }

    static async fetchCheeleeStats(browser, url) {
        // Emulate mobile viewport & touch capabilities matching CHEELEE.json reference recording
        const context = await browser.newContext({
            viewport: { width: 371, height: 737 },
            deviceScaleFactor: 1,
            hasTouch: true,
            isMobile: true,
            userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        });
        const page = await context.newPage();
        try {
            logger.info(`Analiza profilu Cheelee w trybie mobilnym SPA: ${url}`);
            await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 35000 });
            await page.waitForTimeout(6000);

            // Handle ngx-smart-modal / cheelee-get-mobile-app-dialog if present (observed in CHEELEE.json)
            const modalClosed = await page.evaluate(async () => {
                const modal = document.querySelector('ngx-smart-modal, cheelee-get-mobile-app-dialog');
                if (modal) {
                    const backdrop = document.querySelector('.ngx-smart-modal-overlay, ngx-smart-modal > div');
                    if (backdrop) {
                        backdrop.click();
                        return true;
                    }
                }
                return false;
            });

            if (modalClosed) {
                logger.info('Zamknięto modal aplikacji mobilnej Cheelee.');
                await page.waitForTimeout(2000);
            }

            const stats = await page.evaluate(() => {
                const allElements = document.querySelectorAll('span, div, p, cheelee-user-feed-item');
                let followers = 0;
                let likes = 0;
                let views = 0;

                allElements.forEach(el => {
                    const text = el.innerText ? el.innerText.trim() : '';
                    if (/^\d+([.,]\d+)?[KM]?$/i.test(text)) {
                        const parentText = el.parentElement ? el.parentElement.innerText.toLowerCase() : '';
                        if (parentText.includes('follower') || parentText.includes('obserwujący')) {
                            followers = text;
                        } else if (parentText.includes('like') || parentText.includes('polubienia')) {
                            likes = text;
                        } else if (parentText.includes('view') || parentText.includes('wyświetlenia')) {
                            views = text;
                        }
                    }
                });

                return { rawFollowers: followers, rawLikes: likes, rawViews: views };
            });

            return {
                platform: 'Cheelee',
                followers: stats.rawFollowers ? this.parseNumber(stats.rawFollowers) : 0,
                likes: stats.rawLikes ? this.parseNumber(stats.rawLikes) : 0,
                views: stats.rawViews ? this.parseNumber(stats.rawViews) : 0
            };
        } catch (error) {
            logger.error(`Błąd Cheelee Scrapera: ${error.message}`);
            return { platform: 'Cheelee', followers: 0, likes: 0, views: 0 };
        } finally {
            await context.close();
        }
    }

    static async fetchTikTokStats(browser, username) {
        const page = await browser.newPage();
        try {
            logger.info(`Analiza profilu TikTok: @${username}`);
            await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36');
            await page.goto(`https://www.tiktok.com/@${username}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
            await page.waitForTimeout(5000);

            const data = await page.evaluate(() => {
                const scriptEl = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
                if (scriptEl) {
                    try {
                        const json = JSON.parse(scriptEl.innerText);
                        const userInfo = json?.__DEFAULT_SCOPE__?.['webapp.user-detail']?.userInfo;
                        if (userInfo && userInfo.stats) {
                            return {
                                followers: userInfo.stats.followerCount || 0,
                                likes: userInfo.stats.heartCount || 0,
                                views: 0
                            };
                        }
                    } catch (e) {}
                }

                const getVal = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? el.innerText : '0';
                };
                return {
                    followers: getVal('[data-e2e="followers-count"]'),
                    likes: getVal('[data-e2e="likes-count"]'),
                    views: 0
                };
            });

            return {
                platform: 'TikTok',
                followers: typeof data.followers === 'number' ? data.followers : this.parseNumber(data.followers),
                likes: typeof data.likes === 'number' ? data.likes : this.parseNumber(data.likes),
                views: data.views || 0
            };
        } catch (error) {
            logger.error(`Błąd TikTok Scrapera: ${error.message}`);
            return { platform: 'TikTok', followers: 0, likes: 0, views: 0 };
        } finally {
            await page.close();
        }
    }

    static async fetchYouTubeStats(browser, handle) {
        const apiKey = process.env.YOUTUBE_API_KEY;
        if (apiKey) {
            try {
                logger.info(`Pobieranie danych YouTube API v3 dla handla: @${handle}`);
                const res = await axios.get('https://www.googleapis.com/youtube/v3/channels', {
                    params: { part: 'statistics', forHandle: handle, key: apiKey }
                });
                if (res.data && res.data.items && res.data.items.length > 0) {
                    const st = res.data.items[0].statistics;
                    return {
                        platform: 'YouTube',
                        followers: parseInt(st.subscriberCount) || 0,
                        views: parseInt(st.viewCount) || 0,
                        likes: parseInt(st.videoCount) || 0
                    };
                }
            } catch (error) {
                logger.warn(`YouTube API błąd: ${error.message}. Uruchamiam fallback przeglądarkowy.`);
            }
        }

        const page = await browser.newPage();
        try {
            logger.info(`Pobieranie statystyk YouTube przez Playwright dla: @${handle}`);
            await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36');
            await page.goto(`https://www.youtube.com/@${handle}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
            await page.waitForTimeout(4000);

            const ytData = await page.evaluate(() => {
                const subMeta = document.querySelector('meta[itemname="subscribers"]')?.content || 
                                document.querySelector('#subscriber-count')?.innerText || '';
                return { subMeta };
            });

            return {
                platform: 'YouTube',
                followers: this.parseNumber(ytData.subMeta) || 0,
                views: 0,
                likes: 0
            };
        } catch (error) {
            logger.error(`Błąd YouTube Scrapera: ${error.message}`);
            return { platform: 'YouTube', followers: 0, views: 0, likes: 0 };
        } finally {
            await page.close();
        }
    }

    static async run() {
        logger.info('Inicjalizacja przeglądarki Headless (Playwright + Stealth)...');
        const browser = await chromium.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
        });

        try {
            const cheeleeData = await this.fetchCheeleeStats(browser, 'https://web.cheelee.us/users/662316b7141b6c9573c53f3b');
            const tiktokData = await this.fetchTikTokStats(browser, 'FerroART');
            const youtubeData = await this.fetchYouTubeStats(browser, 'FerroART');

            const totalFollowers = cheeleeData.followers + tiktokData.followers + youtubeData.followers;
            const totalLikes = cheeleeData.likes + tiktokData.likes + youtubeData.likes;
            const totalViews = cheeleeData.views + tiktokData.views + youtubeData.views;

            const payload = {
                sources: { cheelee: cheeleeData, tiktok: tiktokData, youtube: youtubeData },
                summary: {
                    aggregatedFollowers: totalFollowers,
                    aggregatedLikes: totalLikes,
                    aggregatedViews: totalViews,
                    timestamp: new Date().toISOString()
                }
            };

            const outDir = path.join(__dirname, '../scripts');
            if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

            const outPath = path.join(outDir, 'stats.json');
            fs.writeFileSync(outPath, JSON.stringify(payload, null, 2));
            logger.info(`Zapisano pomyślnie końcowy plik telemetrii: ${outPath}`);
        } finally {
            await browser.close();
        }
    }
}

ProductionScraper.run().catch(err => {
    logger.error(`Awaria krytyczna skryptu scrapera: ${err.stack}`);
    process.exit(1);
});