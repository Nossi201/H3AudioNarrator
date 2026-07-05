#include "patcher_x86.hpp"
#include "ToolbarRenderer.hpp"
#include "H3Addresses.hpp"
#include "Player.hpp"
#include <H3API.hpp>

using namespace h3;

extern Player g_player;

static const int FRAME_NORMAL  = 0;
static const int FRAME_PRESSED = 1;

bool RectIntersects(int ax, int ay, int aw, int ah, int bx, int by, int bw, int bh)
{
    return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
}

void RequestRedrawToolbarRegion()
{
    __try
    {
        H3WindowManager* wm = P_WindowMgr();
        if (wm && g_toolbar.ready && g_toolbar.absX >= 0)
            THISCALL_5(VOID, H3Addr::H3_REDRAW, wm, g_toolbar.absX, g_toolbar.absY, g_toolbar.w, g_toolbar.h);
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
    }
}

static ToolbarImageKind GetButtonImageKind(ToolbarButtonKind kind)
{
    switch (kind)
    {
    case TB_PREVIOUS:  return IMG_PREVIOUS;
    case TB_PLAYPAUSE: return g_player.IsPlaying() ? IMG_PAUSE : IMG_PLAY;
    case TB_NEXT:      return IMG_NEXT;
    case TB_MENU:      return IMG_MENU;
    }
    return IMG_MENU;
}

static void DrawOneToolbarDef(H3LoadedPcx16* pcx, ToolbarImageKind imgKind, int frame, int x, int y)
{
    if (!pcx || imgKind < 0 || imgKind >= IMG_COUNT)
        return;

    ToolbarDef& td = g_toolbar.defs[imgKind];
    if (!td.loaded || !td.def)
        return;

    if (frame < 0 || frame >= TOOLBAR_STATE_COUNT)
        frame = FRAME_NORMAL;

    __try
    {
        td.def->DrawToPcx16(0, frame, pcx, x, y);
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
    }
}

void DrawToolbar(H3WindowManager* wm, HiHook* h)
{
    if (!wm || !h || !g_toolbar.ready || g_toolbar.absX < 0)
        return;

    H3LoadedPcx16* pcx = wm->GetDrawBuffer();
    if (!pcx)
        return;

    // Czytamy pressed pod blokadą, rysujemy bez niej (blitting jest kosztowny)
    bool pressedSnapshot[TOOLBAR_BTN_COUNT];
    EnterCriticalSection(&g_toolbar.cs);
    for (int i = 0; i < TOOLBAR_BTN_COUNT; i++)
        pressedSnapshot[i] = g_toolbar.btns[i].pressed;
    LeaveCriticalSection(&g_toolbar.cs);

    for (int i = 0; i < TOOLBAR_BTN_COUNT; i++)
    {
        const ToolbarButton& btn = g_toolbar.btns[i];
        ToolbarImageKind imgKind = GetButtonImageKind(btn.kind);
        int state = pressedSnapshot[i] ? FRAME_PRESSED : FRAME_NORMAL;
        DrawOneToolbarDef(pcx, imgKind, state, btn.x, btn.y);
    }

    THISCALL_5(VOID, h->GetDefaultFunc(), wm, g_toolbar.absX, g_toolbar.absY, g_toolbar.w, g_toolbar.h);
}
