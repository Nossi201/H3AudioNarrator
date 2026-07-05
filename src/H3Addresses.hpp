#pragma once
#include <Windows.h>

// Adresy H3 i stale konfiguracyjne wtyczki.
// Wszystkie magiczne liczby zwiazane z silnikiem H3 i ustawieniami
// sa zebrane tutaj — jedno miejsce do zmiany przy portowaniu.

namespace H3Addr {
    static const UINT MSG_DISPLAY    = 0x4F7D20; // H3Messagebox::Display (FASTCALL)
    static const UINT MSG_SHOW       = 0x4F6C00; // H3Messagebox::Show (FASTCALL)
    static const UINT DLG_PROC       = 0x5FF3A0; // H3AdventureMgrDlg::Proc (THISCALL)
    static const UINT DEFAULT_PROC   = 0x41B120; // H3BaseDlg::DefaultProc (THISCALL)
    static const UINT H3_REDRAW      = 0x603190; // H3WindowManager::Redraw (THISCALL)
    static const UINT CURRENT_PLAYER = 0x69CCF4; // wskaznik na indeks koloru aktualnego gracza
    static const UINT H3_HWND_PTR    = 0x699650; // wskaznik na HWND okna gry
}

namespace TextMatch {
    static const int FUZZY_THRESHOLD = 85; // min % podobienstwa do rozmytego dopasowania
    static const int FUZZY_MIN_LEN   = 16; // min dlugosc prefiksu do rozmytego porownania
    static const int NORM_LCS_MIN    = 8;  // min dlugosc normPrefix do fazy 3
}

namespace ToolbarConst {
    static const int DEF_MAX_W       = 700; // max szerokosc DEF-a (ochrona przed 800x600 fallback)
    static const int DEF_MAX_H       = 500; // max wysokosc DEF-a
    static const int DEFAULT_REL_X   = 1080; // fallback pozycja toolbara gdy brak dayText
    static const int DEFAULT_REL_Y   = 638;
    static const int DAY_SHRINK_MIN  = 40;  // min szerokosc dayText po zwezeniu
    static const int RES_BAR_ID      = 1000; // ID kontrolki paska zasobow w dialogs H3
    static const int DATE_TEXT_ID    = 1008; // ID kontrolki daty
}
