#include "ToolbarLayout.hpp"
#include "ToolbarRenderer.hpp"
#include "ButtonPlugin.hpp"
#include "H3Addresses.hpp"
#include <H3API.hpp>
#include <string>

using namespace h3;

extern ButtonPlugin buttonPlugin;
extern std::string GetDllDir();

static const int TOOLBAR_GAP      = 0;
static const int TOOLBAR_OFFSET_X = 0;
static const int TOOLBAR_OFFSET_Y = 0;

//===================================================================================
//                       LADOWANIE PAKA LOD I DEF-OW
//===================================================================================

void LoadToolbarDefs(ButtonPlugin& plugin)
{
    if (g_toolbar.packLodsLoaded)
        return;

    g_toolbar.packLodsLoaded = true;

    typedef INT(__stdcall* LoadLodsFromFolderProc)(LPCSTR path);

    UINT32 fn = plugin.VarGetValue<UINT32>("LodTable.Function", 0);
    if (!fn)
    {
        plugin.Log("[ToolbarDEF] LodTable.Function=NULL - H3.LodTable.dll nie udostepnil funkcji");
        return;
    }

    std::string dllDir = GetDllDir();
    LoadLodsFromFolderProc loadFolder = reinterpret_cast<LoadLodsFromFolderProc>(fn);
    INT loaded = loadFolder(dllDir.c_str());

    plugin.LogFormat("[ToolbarDEF] LodTable.Function('%s') => %d LOD/PAC", dllDir.c_str(), loaded);
}

static INT GetCurrentPlayerColorId()
{
    INT player = 0;
    __try
    {
        player = *(UINT*)H3Addr::CURRENT_PLAYER;
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        player = 0;
    }
    if (player < 0 || player > 7) player = 0;
    return player;
}

static bool LoadOneToolbarDef(ToolbarImageKind img, const char* defName)
{
    ToolbarDef& td = g_toolbar.defs[img];
    td.name = defName;
    td.def = H3LoadedDef::Load(defName);
    td.loaded = false;
    td.width = 0;
    td.height = 0;

    if (!td.def)
    {
        buttonPlugin.LogFormat("[ToolbarDEF] %s => FAIL/NULL", defName);
        return false;
    }

    td.width  = td.def->widthDEF;
    td.height = td.def->heightDEF;

    if (td.width <= 0 || td.height <= 0 || td.width >= ToolbarConst::DEF_MAX_W || td.height >= ToolbarConst::DEF_MAX_H)
    {
        buttonPlugin.LogFormat("[ToolbarDEF] %s => INVALID %dx%d", defName, td.width, td.height);
        return false;
    }

    __try { td.def->ColorToPlayer(GetCurrentPlayerColorId()); }
    __except (EXCEPTION_EXECUTE_HANDLER) {}

    td.loaded = true;
    buttonPlugin.LogFormat("[ToolbarDEF] %s => OK %dx%d groups=%d", defName, td.width, td.height, td.def->groupsCount);
    return true;
}

static bool LoadToolbarDefsOnce()
{
    if (g_toolbar.defsLoaded)
        return true;

    g_toolbar.defsLoaded = true;
    LoadToolbarDefs(buttonPlugin);

    // Nazwy bez prefiksu "BTN" - zgodne z tym, co faktycznie jest spakowane
    // w TD.lod (zweryfikowane 2026-07-02 przez odczyt naglowka LOD). F6
    // (PlayerDlg.cpp) uzywa osobnego zestawu z sufiksem "_B" (PREV_B.def itd.),
    // ktory zostaje bez zmian - to inne DEF-y, nie duplikat tych samych nazw.
    bool ok = true;
    ok = LoadOneToolbarDef(IMG_PREVIOUS, "PREV.DEF") && ok;
    ok = LoadOneToolbarDef(IMG_PLAY,     "PLAY.DEF") && ok;
    ok = LoadOneToolbarDef(IMG_PAUSE,    "PAUS.DEF") && ok;
    ok = LoadOneToolbarDef(IMG_NEXT,     "NEXT.DEF") && ok;
    ok = LoadOneToolbarDef(IMG_MENU,     "MENU.DEF") && ok;

    if (ok)
        g_toolbar.colorPlayer = GetCurrentPlayerColorId();

    return ok;
}

static void RefreshToolbarDefsIfPlayerChanged()
{
    INT player = GetCurrentPlayerColorId();
    if (!g_toolbar.defsLoaded || g_toolbar.colorPlayer == -1 || player == g_toolbar.colorPlayer)
        return;

    for (INT i = 0; i < IMG_COUNT; i++)
    {
        g_toolbar.defs[i].def    = nullptr;
        g_toolbar.defs[i].loaded = false;
        g_toolbar.defs[i].width  = 0;
        g_toolbar.defs[i].height = 0;
    }

    g_toolbar.defsLoaded = false;
    g_toolbar.ready = false;
    LoadToolbarDefsOnce();
}

//===================================================================================
//                       OBLICZANIE POZYCJI I HIT-TEST
//===================================================================================

static INT DefWidth(ToolbarImageKind img)  { return g_toolbar.defs[img].loaded ? g_toolbar.defs[img].width : 0; }
static INT DefHeight(ToolbarImageKind img) { return g_toolbar.defs[img].loaded ? g_toolbar.defs[img].height : 0; }
static INT MaxInt(INT a, INT b)            { return a > b ? a : b; }

static INT PlayPauseSlotWidth()  { return MaxInt(DefWidth(IMG_PLAY),  DefWidth(IMG_PAUSE)); }
static INT PlayPauseSlotHeight() { return MaxInt(DefHeight(IMG_PLAY), DefHeight(IMG_PAUSE)); }

static INT ToolbarTotalWidth()
{
    return DefWidth(IMG_PREVIOUS)
         + PlayPauseSlotWidth()
         + DefWidth(IMG_NEXT)
         + DefWidth(IMG_MENU)
         + TOOLBAR_GAP * 3;
}

static INT ToolbarMaxHeight()
{
    INT h = 0;
    for (INT img = 0; img < IMG_COUNT; img++)
        if (g_toolbar.defs[img].loaded && g_toolbar.defs[img].height > h)
            h = g_toolbar.defs[img].height;
    return h;
}

static bool ComputeToolbarPosition(H3AdventureMgrDlg* advDlg)
{
    if (!advDlg || !LoadToolbarDefsOnce())
        return false;

    H3ResourceBarPanel* rb  = advDlg->resourceBar;
    H3DlgText* dayText      = rb ? rb->currentDayText : nullptr;

    INT totalW = ToolbarTotalWidth();
    INT maxH   = ToolbarMaxHeight();
    if (totalW <= 0 || maxH <= 0)
        return false;

    INT relX = ToolbarConst::DEFAULT_REL_X;
    INT relY = ToolbarConst::DEFAULT_REL_Y;

    if (dayText)
    {
        if (!g_toolbar.dateTextAdjusted)
        {
            INT oldW = dayText->GetWidth();
            INT newW = oldW - totalW;
            if (newW > ToolbarConst::DAY_SHRINK_MIN && newW != oldW)
            {
                dayText->SetWidth((UINT16)newW);
                __try
                {
                    advDlg->RedrawItem(ToolbarConst::RES_BAR_ID);
                    advDlg->RedrawItem(ToolbarConst::DATE_TEXT_ID);
                    H3WindowManager* wm = P_WindowMgr();
                    if (wm)
                        THISCALL_5(VOID, H3Addr::H3_REDRAW, wm, 0, 0, 8000, 8000);
                }
                __except (EXCEPTION_EXECUTE_HANDLER) {}
            }
            g_toolbar.dateTextAdjusted = true;
        }

        INT absX = dayText->GetAbsoluteX() + dayText->GetWidth() + TOOLBAR_OFFSET_X + 4;
        INT absY = dayText->GetAbsoluteY() - 4 + TOOLBAR_OFFSET_Y;

        relX = absX - advDlg->GetX();
        relY = absY - advDlg->GetY();
    }

    INT x    = advDlg->GetX() + relX;
    INT y    = advDlg->GetY() + relY;
    INT curX = x;

    g_toolbar.btns[TB_PREVIOUS].kind = TB_PREVIOUS;
    g_toolbar.btns[TB_PREVIOUS].x    = curX;
    g_toolbar.btns[TB_PREVIOUS].y    = y;
    g_toolbar.btns[TB_PREVIOUS].w    = DefWidth(IMG_PREVIOUS);
    g_toolbar.btns[TB_PREVIOUS].h    = DefHeight(IMG_PREVIOUS);
    curX += g_toolbar.btns[TB_PREVIOUS].w + TOOLBAR_GAP;

    g_toolbar.btns[TB_PLAYPAUSE].kind = TB_PLAYPAUSE;
    g_toolbar.btns[TB_PLAYPAUSE].x    = curX;
    g_toolbar.btns[TB_PLAYPAUSE].y    = y;
    g_toolbar.btns[TB_PLAYPAUSE].w    = PlayPauseSlotWidth();
    g_toolbar.btns[TB_PLAYPAUSE].h    = PlayPauseSlotHeight();
    curX += g_toolbar.btns[TB_PLAYPAUSE].w + TOOLBAR_GAP;

    g_toolbar.btns[TB_NEXT].kind = TB_NEXT;
    g_toolbar.btns[TB_NEXT].x    = curX;
    g_toolbar.btns[TB_NEXT].y    = y;
    g_toolbar.btns[TB_NEXT].w    = DefWidth(IMG_NEXT);
    g_toolbar.btns[TB_NEXT].h    = DefHeight(IMG_NEXT);
    curX += g_toolbar.btns[TB_NEXT].w + TOOLBAR_GAP;

    g_toolbar.btns[TB_MENU].kind = TB_MENU;
    g_toolbar.btns[TB_MENU].x    = curX;
    g_toolbar.btns[TB_MENU].y    = y;
    g_toolbar.btns[TB_MENU].w    = DefWidth(IMG_MENU);
    g_toolbar.btns[TB_MENU].h    = DefHeight(IMG_MENU);

    g_toolbar.absX  = x;
    g_toolbar.absY  = y;
    g_toolbar.w     = totalW;
    g_toolbar.h     = maxH;
    g_toolbar.ready = true;

    return true;
}

void EnsureToolbar(H3AdventureMgrDlg* advDlg)
{
    if (!advDlg)
        return;

    RefreshToolbarDefsIfPlayerChanged();

    if (advDlg != g_toolbar.boundAdventureDlg)
    {
        g_toolbar.boundAdventureDlg = advDlg;
        g_toolbar.ready             = false;
        g_toolbar.absX = g_toolbar.absY = -1;
        g_toolbar.w = g_toolbar.h       = 0;
        g_toolbar.dateTextAdjusted      = false;
        g_toolbar.SafeClearAllPressed();
    }

    if (!g_toolbar.ready)
    {
        if (ComputeToolbarPosition(advDlg))
            RequestRedrawToolbarRegion();
    }
}

int HitToolbarButton(int x, int y)
{
    if (!g_toolbar.ready)
        return -1;

    for (int i = 0; i < TOOLBAR_BTN_COUNT; i++)
    {
        const ToolbarButton& b = g_toolbar.btns[i];
        if (x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h)
            return i;
    }
    return -1;
}

bool IsAdventureMapForeground()
{
    __try
    {
        // Tylko status managera mapy przygody - NIE porownujemy z wm->lastDlg.
        // Dymki H3Messagebox (np. "nowy dzien", dialogi questowe) sa osobnymi,
        // tymczasowymi oknami stawianymi NAD dialogiem mapy przygody - w trakcie
        // ich wyswietlania wm->lastDlg wskazuje na nie, a nie na adv->dlg, mimo
        // ze wciaz jestesmy na mapie przygody (adv->dlg pozostaje aktywnym
        // dialogiem-wlascicielem). Porownanie z lastDlg falszywie rozpoznawalo
        // to jako "opuszczenie mapy" i gasilo pasek przy kazdym takim oknie.
        // Status managera (ACTIVE/DISABLED/DESTROYED) zmienia sie tylko przy
        // faktycznym niszczeniu/tworzeniu managera mapy przygody (powrot do
        // menu glownego), nie przy tymczasowych dialogach nad nim.
        H3AdventureManager* adv = P_AdventureMgr();
        return adv && adv->status == H3Manager::ACTIVE && adv->dlg;
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        return false;
    }
}
