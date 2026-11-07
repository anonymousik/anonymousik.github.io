echo "Ustawienoie trybu wyjścia HDR na 'auto'"
adb shell settings put global hdr_output_mode auto

echo "Aktywacja statycznych metadanych HDR (MaxCLL/MaxFALL)"
adb shell settings put global hdr_static_metadata 1

echo "Wymuszenie przestrzeni kolorów BT.2020 na złączu HDMI"
adb shell settings put global hdmi_color_space bt2020

echo "Aktywacja krzywej tonalnej PQ (SMPTE ST 2084) dla potoku EOTF"
adb shell settings put global hdmi_eotf smpte2084

