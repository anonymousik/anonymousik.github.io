echo " Ustawienie trybu wyjścia HDR na 'auto'"
adb shell setprop persist.sys.display.hdr_mode auto

echo " Wymuszenie przestrzeni kolorów BT.2020 i krzywej PQ (ST2084)"
adb shell setprop persist.sys.display.color_space bt2020
adb shell setprop persist.sys.display.eotf smpte2084

echo "Wstrzyknięcie statycznych metadanych HDR (MaxCLL / MaxFALL / Min Luminance)"
adb shell setprop persist.sys.display.max_cll 1000
adb shell setprop persist.sys.display.max_fall 400
adb shell setprop persist.sys.display.min_luminance 0.0050

echo " Flaga wymuszająca priorytetyzację trybu HDR (często wymagana na STB operatorów)"
adb shell setprop persist.sys.display.hdr_enable true
adb shell setprop persist.vendor.display.hdr_mode auto
adb shell setprop persist.vendor.display.color_space bt2020

