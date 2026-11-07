echo "[+] Resetowanie usług OMX i czyszczenie pamięci podręcznej..."

# Czyszczenie bazy danych i pamięci podręcznej dostawców multimediów
./rish -c "pm clear com.android.providers.media"
./rish -c "pm clear com.android.providers.media.module"

# Wymuszenie restartu demona multimediów (Android automatycznie go zrestartuje z czystą pamięcią)
./rish -c "killall android.hardware.media.omx@1.0-service"
./rish -c "killall mediaserver"

echo "[+] Usługi multimedialne zostały odświeżone."

