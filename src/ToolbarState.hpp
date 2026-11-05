#pragma once
#include <Windows.h>

// Identyfikatory przycisków toolbara (pozycja na pasku)
#define TOOLBAR_BTN_COUNT   4
#define TOOLBAR_STATE_COUNT 2

enum ToolbarButtonKind { TB_PREVIOUS = 0, TB_PLAYPAUSE, TB_NEXT, TB_MENU };
enum ToolbarImageKind  { IMG_PREVIOUS = 0, IMG_PLAY, IMG_PAUSE, IMG_NEXT, IMG_MENU, IMG_COUNT };

// Forward-declare w namespace h3 zamiast pelnego include — uzywamy tylko wskaznikow
namespace h3 {
    struct H3LoadedDef;
    struct H3AdventureMgrDlg;
}

struct ToolbarDef {
    const char*      name;
    h3::H3LoadedDef* def;
    int              width;
    int              height;
    bool             loaded;

    ToolbarDef() : name(nullptr), def(nullptr), width(0), height(0), loaded(false) {}
};

struct ToolbarButton {
    ToolbarButtonKind kind;
    int  x, y, w, h;
    bool pressed;

    ToolbarButton() : kind(TB_MENU), x(-1), y(-1), w(0), h(0), pressed(false) {}
};

// Caly stan toolbara w jednej strukturze.
// CRITICAL_SECTION cs chroni dostep do btns[].pressed:
//   zapis z watku WH_MOUSE_LL, odczyt z watku gry (DrawToolbar).
struct ToolbarState {
    ToolbarDef         defs[IMG_COUNT];
    ToolbarButton      btns[TOOLBAR_BTN_COUNT];

    bool               defsLoaded;
    int                colorPlayer;
    bool               packLodsLoaded;
    bool               ready;
    h3::H3AdventureMgrDlg* boundAdventureDlg;
    int                absX, absY, w, h;
    // Oryginalna (niezwezona) szerokosc tekstu daty i wskaznik kontrolki, dla
    // ktorej ja zapamietano - pasek zweza date zawsze wzgledem tej wartosci,
    // nigdy wzgledem biezacej (patrz ComputeToolbarPosition).
    const void*        dayTextPtr;
    int                dayTextOrigW;

    // Chroniony przez cs: btns[i].pressed
    CRITICAL_SECTION   cs;

    ToolbarState();
    ~ToolbarState();

    // Wywolac z cs posiadanym przez wywolujacego LUB uzyc SafeSetPressed/SafeClearAll.
    void SafeSetPressed(int idx, bool val);
    bool SafeGetPressed(int idx) const;
    void SafeClearAllPressed(bool* changedOut = nullptr);
};

extern ToolbarState g_toolbar;
