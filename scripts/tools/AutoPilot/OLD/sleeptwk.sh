#!/system/bin/sh
# ==============================================================================
#  PROJECT: PLAYBOX TITANIUM - SMART ONE-LINER TWEAKER (v15.8)
#  TARGET:  Sagemcom DCTIW362P | Android 9 | VideoCore IV
#  GOAL:    Anti-Sleep, Accessibility Protection, Performance Optimization
# ==============================================================================

L_BLUE='\033[94m'
L_GREEN='\033[92m'
L_CLR='\033[0m'

echo "${L_BLUE}# Starting Smart-One-Liner (Fusion v15.8)...${L_CLR}"

# --- [1] ACCESSIBILITY & BATTERY OPTIMIZATION ---
# Target: SmartTube & Accessibility Mappers
PKG="org.smarttube.stable"
echo "  -> Protecting Accessibility & Apps..."
dumpsys deviceidle whitelist +$PKG
am set-standby-bucket $PKG active
cmd appops set $PKG RUN_IN_BACKGROUND allow
cmd appops set $PKG START_FOREGROUND allow

# --- [2] ANTI-SLEEP & HDMI-CEC PROTOCOL ---
echo "  -> Applying Anti-Sleep Fixes..."
settings put secure sleep_timeout 2147483647
settings put system screen_off_timeout 2147483647
settings put global stay_on_while_plugged_in 3
settings put global hdmi_control_auto_device_off_enabled 0
settings put global hdmi_control_auto_tv_off_enabled 1
settings put system intelligent_sleep_mode 0

# --- [3] VIDEOCORE IV PERFORMANCE PIPELINE ---
echo "  -> Tuning VC4 GPU & SurfaceFlinger..."
setprop debug.hwui.renderer skiagl
setprop debug.sf.latch_unsignaled 1
setprop debug.sf.disable_backpressure 1
setprop debug.sf.early_gl_phase_offset_ns 3000000
# Force bypass of HWC bug on BCM72604
service call SurfaceFlinger 1008 i32 1 > /dev/null

# --- [4] UI & NETWORK RESPONSE TWEAKS ---
echo "  -> Minimizing UI Latency..."
settings put global window_animation_scale 0.2
settings put global transition_animation_scale 0.25
settings put global animator_duration_scale 0.5
settings put secure accessibility_interactive_ui_timeout_ms 2000
settings put secure accessibility_non_interactive_ui_timeout_ms 3000

# Secure DNS (Cloudflare) from ghost-input-purge.py
settings put global private_dns_mode hostname
settings put global private_dns_specifier one.one.one.one

# --- [5] MEMORY & GMS PURGE ---
echo "  -> Cleaning Memory Footprint..."
pm trim-caches 512M
am kill com.google.android.gms
am kill com.android.vending

echo "${L_GREEN}# SUCCESS: Sagemcom DCTIW362P is now Optimized & Sleep-Proof.${L_CLR}"