adb shell "
# 1. Trwałe limity procesów i pamięci RAM (idealny balans: SmartTube + Chromecast + Launcher)
settings put global activity_manager_constants 'max_cached_processes=4,background_settle_time=20000,fgservice_min_shown_time=100,power_check_max_cpu_1=35,power_check_max_cpu_0=45'
settings put global low_ram false
settings put global always_finish_activities 0
settings put global low_power 0
settings put global low_power_trigger_level 0
settings put global stay_on_while_plugged_in 3

# 2. Trwała blokada odświeżania 1080p 60Hz (zapobiega powrotowi do 25Hz PAL po restarcie)
wm size 1920x1080
settings put system display_peak_refresh_rate 60.0
settings put system min_refresh_rate 60.0
settings put system user_refresh_rate 60.0
settings put global window_animation_scale 0.0
settings put global transition_animation_scale 0.2
settings put global animator_duration_scale 0.2

# 3. Trwałe audio PCM Stereo (eliminuje przycięcia przy szybkim przewijaniu)
settings put global encoded_surround_output 1
settings put global encoded_surround_output_enabled 0
settings put system sound_effects_enabled 0

# 4. Trwała stabilizacja Wi-Fi 5 GHz + wyciszenie spamu Wi-Fi HAL + DoT Cloudflare
settings put global wifi_sleep_policy 2
settings put global wifi_power_save 0
settings put global wifi_scan_always_enabled 0
settings put global ble_scan_always_enabled 0
settings put global wifi_watchdog_on 0
settings put secure wifi_watchdog_poor_link_detection 0
settings put global captive_portal_mode 0
settings put global netstats_enabled 0
settings put global prefer_ipv4 true
settings put global private_dns_mode hostname
settings put global private_dns_specifier one.one.one.one
settings put global net.tcp.buffersize.wifi '524288,1048576,2097152,262144,524288,1048576'
settings put global net.tcp.buffersize.default '524288,1048576,2097152,262144,524288,1048576'

# 5. Trwała ochrona SmartTube, Projectivy Launcher i Chromecast (Cast-Safe)
dumpsys deviceidle whitelist +org.smarttube.stable
dumpsys deviceidle whitelist +com.spocky.projengmenu
dumpsys deviceidle whitelist +com.google.android.apps.mediashell
dumpsys deviceidle whitelist +com.google.android.gms
am set-standby-bucket org.smarttube.stable active
am set-standby-bucket com.spocky.projengmenu active
am set-standby-bucket com.google.android.apps.mediashell active
cmd appops set org.smarttube.stable WAKE_LOCK allow
cmd appops set org.smarttube.stable RUN_ANY_IN_BACKGROUND allow
cmd appops set com.google.android.gms WAKE_LOCK ignore
cmd appops set com.google.android.gms CHANGE_NETWORK_STATE ignore

# 6. Trwała kompilacja AOT do kodu maszynowego ARMv7 (przetrwa restarty aż do aktualizacji aplikacji)
cmd package compile -m speed-profile -f org.smarttube.stable
cmd package compile -m speed-profile -f com.spocky.projengmenu
cmd package compile -m speed-profile -f com.google.android.apps.mediashell
"

