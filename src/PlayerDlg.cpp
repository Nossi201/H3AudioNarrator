#include "PlayerDlg.hpp"
#include <cstdio>
#include <cstring>

using namespace h3;

extern Player       g_player;
extern ButtonPlugin buttonPlugin;
extern std::string  g_settingsPath;

// ============================================================================
//  Stałe geometryczne
// ============================================================================

static constexpr INT ITEM_H = 18;
static constexpr INT SB_W   = 15;
static constexpr INT LIST_Y = 36;
static constexpr INT LIST_H = PlayerDlg::N_VISIBLE * ITEM_H;  // 12×18=216

// Panel prawy: scrollbar przylega do prawego paddingu (DLG_W-21=455)
static constexpr INT RL_SB_X   = PlayerDlg::DLG_W - 21 - SB_W;           // 440
static constexpr INT RL_ITEM_W = RL_SB_X - PlayerDlg::PR_X - 2;           // 175

// Przyciski Play/Reset i [<<][>>], oba rzędy w lewym panelu — 64×30 = rozmiar iOkay.def / BOX_64_30_PCX
static constexpr INT BTN_W    = 64;
static constexpr INT BTN_H    = 30;
static constexpr INT BTN_GAP  = 9;
static constexpr INT BTN2_TOT = 2 * BTN_W + 1 * BTN_GAP;                  // 137
static constexpr INT BTN_X0   = PlayerDlg::PC_X + (PlayerDlg::PC_W - BTN2_TOT) / 2;
static constexpr INT BTN_ROW_GAP = 8;

// Stopka - liczona pierwsza, przyciski podwieszone od niej w górę (bez martwej przestrzeni)
static constexpr INT FOOTER_BTN_X = (PlayerDlg::DLG_W - 64) / 2;          // 206
static constexpr INT FOOTER_BTN_Y = PlayerDlg::DLG_H - 24 - 30;           // 264
static constexpr INT FOOTER_SEP_Y = FOOTER_BTN_Y - 6;                     // 258

static constexpr INT BTN_Y    = FOOTER_SEP_Y - 8 - BTN_H;                 // 220 - rząd [<<][>>] (bliżej stopki)
static constexpr INT BTN_Y2   = BTN_Y - BTN_H - BTN_ROW_GAP;              // 182 - rząd Play/Reset (wyżej)

// ============================================================================
//  Separatory - DarkenArea/LightenArea zamiast CreateLineSeparator (stripe3d.bmp).
//  Te same prymitywy co natywne H3LoadedPcx16::SinkArea/BevelArea: modyfikują
//  istniejące piksele tła (cień+highlight) zamiast nadpisywać je płaskim kolorem.
// ============================================================================

static void DrawGrooveH(H3LoadedPcx16* bg, INT x, INT y, INT w)
{
    if (!bg) return;
    bg->DarkenArea(x, y,     w, 1, 50);
    bg->LightenArea(x, y + 1, w, 1, 50);
}

static void DrawGrooveV(H3LoadedPcx16* bg, INT x, INT y, INT h)
{
    if (!bg) return;
    bg->DarkenArea(x,     y, 1, h, 50);
    bg->LightenArea(x + 1, y, 1, h, 50);
}

// ============================================================================
//  Konstruktor
// ============================================================================

PlayerDlg::PlayerDlg()
    : H3Dlg(DLG_W, DLG_H)
    , m_rightScroll(0), m_lastTick(-1), m_wasPlaying(false)
{
}

// ============================================================================
//  OnCreate
// ============================================================================

BOOL PlayerDlg::OnCreate()
{
    // ========================================================================
    //  PANEL KONTROLEK (lewy, PC_X=21, PC_W=240)
    // ========================================================================

    H3LoadedPcx16* bg = GetBackgroundPcx();

    // Gorny border jednym wywolaniem na pelnej szerokosci (bez przerwy przy pionowej linii)
    DrawGrooveH(bg, PC_X - 7, 28, (PR_X + PR_W + 7) - (PC_X - 7));

    // Pionowa linia między lewym a prawym panelem (wypełnia 2px odstęp: PC_X+PC_W=261 do PR_X=263)
    DrawGrooveV(bg, PC_X + PC_W, 30, 229);

    // Głośność – etykieta + suwak (odsunięte 7px od lewej krawędzi)
    CreateText(PC_X + 7, 36, PC_W - 7, 16,
        "Vol: 50%",
        NH3Dlg::Text::SMALL, NH3Dlg::NTextColor::WHITE, ID_TEXT_VOLUME,
        NH3Dlg::NTextAlignment::MIDDLE_LEFT);

    {
        H3DlgScrollbar* sb = CreateScrollbar(
            PC_X + 16, 54, PC_W - 16, 16,
            ID_SCROLLBAR_VOL,
            /*ticksCount=*/100,
            VolumeScrollProc,
            /*isBlue=*/FALSE,
            /*stepSize=*/0,
            /*arrowsEnabled=*/TRUE
        );
        if (sb)
        {
            sb->SetTick(g_player.GetSettings().volume / 10);
            sb->SetButtonPosition();
        }
    }

    // Czas audio – etykieta + suwak (seek) (odsunięte 7px od lewej krawędzi)
    CreateText(PC_X + 7, 78, PC_W - 7, 16,
        "Czas: 0:00 / 0:00",
        NH3Dlg::Text::SMALL, NH3Dlg::NTextColor::WHITE, ID_TEXT_TIME,
        NH3Dlg::NTextAlignment::MIDDLE_LEFT);

    CreateScrollbar(
        PC_X + 16, 96, PC_W - 16, 16,
        ID_SEEK_SLIDER,
        /*ticksCount=*/1000,
        SeekSliderProc,
        /*isBlue=*/FALSE,
        /*stepSize=*/0,
        /*arrowsEnabled=*/FALSE
    );

    // Autoplay – natywny checkbox H3 (sysopchk.def, 32×24) + etykieta.
    // Jeden przelacznik odpowiedzialny za wszystko: auto-play dialogow kampanii,
    // auto-advance playlisty PO ZAKONCZENIU utworu, oraz czy klik na wiersz/next/prev
    // odtwarzaja od razu (ON) czy tylko zaznaczaja (OFF).
    {
        bool on = g_player.GetSettings().auto_start;
        CreateOnOffCheckbox(PC_X, 124, ID_BTN_AUTOPLAY, on ? 1 : 0, on ? 0 : 1);
        CreateText(PC_X + 36, 124, PC_W - 36, 26,
            "Autoplay",
            NH3Dlg::Text::SMALL, NH3Dlg::NTextColor::WHITE,
            ID_TEXT_AUTOPLAY, NH3Dlg::NTextAlignment::MIDDLE_LEFT);
    }

    // Separator przed przyciskami (wspólny dla obu rzędów: Play/Reset i [<<][>>])
    DrawGrooveH(bg, PC_X - 7, BTN_Y2 - 8, PC_W + 7);

    // Rząd 1: Play/Paus (toggle) + Reset – z BOX_64_30_PCX
    {
        INT bx = BTN_X0;
        AddItem(H3DlgPcx::Create(bx - 1, BTN_Y2 - 1, NH3Dlg::Assets::BOX_64_30_PCX));
        AddItem(H3DlgDefButton::Create(bx, BTN_Y2, BTN_W, BTN_H, ID_BTN_PLAY,  "PLAY_B.def",  0, 1, FALSE, 0));
        bx += BTN_W + BTN_GAP;
        AddItem(H3DlgPcx::Create(bx - 1, BTN_Y2 - 1, NH3Dlg::Assets::BOX_64_30_PCX));
        AddItem(H3DlgDefButton::Create(bx, BTN_Y2, BTN_W, BTN_H, ID_BTN_RESET, "RESET_B.def", 0, 1, FALSE, 0));
    }

    // Rząd 2: [<<][>>] (Previous/Next) – ten sam x co rząd wyżej, niższy o BTN_H+BTN_ROW_GAP
    {
        INT bx = BTN_X0;
        AddItem(H3DlgPcx::Create(bx - 1, BTN_Y - 1, NH3Dlg::Assets::BOX_64_30_PCX));
        AddItem(H3DlgDefButton::Create(bx, BTN_Y, BTN_W, BTN_H, ID_BTN_Q_PREV, "PREV_B.def", 0, 1, FALSE, 0));
        bx += BTN_W + BTN_GAP;
        AddItem(H3DlgPcx::Create(bx - 1, BTN_Y - 1, NH3Dlg::Assets::BOX_64_30_PCX));
        AddItem(H3DlgDefButton::Create(bx, BTN_Y, BTN_W, BTN_H, ID_BTN_Q_NEXT, "NEXT_B.def", 0, 1, FALSE, 0));
    }

    // ========================================================================
    //  PANEL PLAYLISTA (prawy, PR_X=263, PR_W=192, scrollbar do x=455)
    // ========================================================================

    for (INT i = 0; i < N_VISIBLE; i++)
    {
        CreateText(PR_X + 7, LIST_Y + i * ITEM_H, RL_ITEM_W - 7, ITEM_H,
            "",
            NH3Dlg::Text::SMALL, NH3Dlg::NTextColor::WHITE,
            ID_RIGHT_ITEM_BASE + i,
            NH3Dlg::NTextAlignment::MIDDLE_LEFT);
    }

    CreateScrollbar(
        RL_SB_X, LIST_Y, SB_W + 1, LIST_H,  // +1: kompensuje 1px niedoboru toru z prawej strony
        ID_SCROLL_RIGHT,
        /*ticksCount=*/250,
        ScrollRightProc,
        /*isBlue=*/FALSE,
        /*stepSize=*/1,
        /*arrowsEnabled=*/TRUE
    );

    // ========================================================================
    //  STOPKA (pełna szerokość, padding dół 24px)
    // ========================================================================

    DrawGrooveH(bg, 5 + 9, FOOTER_SEP_Y, DLG_W - 10 - 18);
    CreateOKButton(FOOTER_BTN_X, FOOTER_BTN_Y);

    UpdateRightList();
    UpdateCenter();

    return TRUE;
}

// ============================================================================
//  OnLeftClick
// ============================================================================

BOOL PlayerDlg::OnLeftClick(INT itemId, H3Msg& msg)
{
    // Klik na wiersz playlisty: przy Autoplay ON odtwarza od razu (stare zachowanie),
    // przy Autoplay OFF tylko zaznacza (trzeba nacisnac Play zeby odtworzyc).
    if (itemId >= ID_RIGHT_ITEM_BASE && itemId < ID_RIGHT_ITEM_BASE + N_VISIBLE)
    {
        int absIdx = m_rightScroll + (itemId - ID_RIGHT_ITEM_BASE);
        Settings& s = g_player.GetSettings();
        const std::vector<std::string>& ids = s.GetCurrentUnlocked();
        if (absIdx < (int)ids.size())
        {
            if (s.auto_start)
            {
                g_player.Play(ids[absIdx]);
                UpdateCenter();
                RequestRedrawToolbarRegion();
            }
            else
            {
                s.selected_audio = ids[absIdx];
                s.Save(g_settingsPath.c_str());
            }
            UpdateRightList();
        }
        return FALSE;
    }

    switch (itemId)
    {
    case ID_BTN_PLAY:
        // Pauza/wznowienie zachowuje pozycje (kontynuacja), nie restartuje od 0.
        g_player.TogglePlayPause();
        UpdateCenter();
        UpdateRightList();
        RequestRedrawToolbarRegion();
        return FALSE;

    case ID_BTN_RESET:
        g_player.Reset();
        UpdateCenter();
        RequestRedrawToolbarRegion();
        return FALSE;

    case ID_BTN_AUTOPLAY:
    {
        Settings& s = g_player.GetSettings();
        s.auto_start = !s.auto_start;
        s.Save(g_settingsPath.c_str());
        // Ustaw frame checkboxa ręcznie (persistent toggle)
        if (H3DlgDefButton* cb = GetDefButton(ID_BTN_AUTOPLAY))
        {
            cb->SetFrame(s.auto_start ? 1 : 0);
            cb->SetClickFrame(s.auto_start ? 0 : 1);
        }
        Redraw();
        return FALSE;
    }

    case ID_BTN_Q_PREV:
        g_player.PlayPrevious();
        UpdateCenter();
        UpdateRightList();
        RequestRedrawToolbarRegion();
        return FALSE;

    case ID_BTN_Q_NEXT:
        g_player.PlayNext();
        UpdateCenter();
        UpdateRightList();
        RequestRedrawToolbarRegion();
        return FALSE;

    default:
        return TRUE;   // OK zamknie dialog
    }
}

// ============================================================================
//  DialogProc
// ============================================================================

BOOL PlayerDlg::DialogProc(H3Msg& msg)
{
    g_player.Update();

    // Suwak seek: przelicz aktualną pozycję
    int dur     = g_player.GetCurrentDuration();
    int pos     = g_player.current_time;
    int newTick = (dur > 0) ? (int)((INT64)pos * 1000 / dur) : 0;

    if (H3DlgScrollbar* sb = GetScrollbar(ID_SEEK_SLIDER))
    {
        sb->SetTick(newTick);
        sb->SetButtonPosition();
    }

    // Redraw gdy zmienił się tick lub ID odtwarzanego tracka
    std::string currentId = g_player.GetCurrentAudioId();
    bool changed  = (newTick != m_lastTick) || (currentId != m_lastAudioId);
    if (changed)
    {
        m_lastTick    = newTick;
        m_lastAudioId = currentId;
        UpdateCenter();
        UpdateRightList();
    }

    return FALSE;
}

// ============================================================================
//  UpdateRightList
// ============================================================================

void PlayerDlg::UpdateRightList()
{
    const std::vector<std::string>& ids = g_player.GetSettings().GetCurrentUnlocked();
    int total                           = (int)ids.size();

    int maxScroll = (total > N_VISIBLE) ? (total - N_VISIBLE) : 0;
    if (m_rightScroll > maxScroll) m_rightScroll = maxScroll;
    if (m_rightScroll < 0)         m_rightScroll = 0;

    if (H3DlgScrollbar* sb = GetScrollbar(ID_SCROLL_RIGHT))
        sb->SetTick(m_rightScroll);

    // Jeden marker (GOLD): odtwarzany, a gdy nic aktualnie NIE GRA (w tym gdy cos
    // jest tylko wstrzymane) - ostatnio zaznaczony/wybrany. Sprawdzamy IsPlaying(),
    // nie samo "czy GetCurrentAudioId niepuste" - inaczej wstrzymany utwor
    // blokowalby podswietlenie nowego zaznaczenia w nieskonczonosc.
    std::string activeId = g_player.IsPlaying() ? g_player.GetCurrentAudioId()
                                                 : g_player.GetSettings().selected_audio;

    for (INT i = 0; i < N_VISIBLE; i++)
    {
        H3DlgText* t = GetText(ID_RIGHT_ITEM_BASE + i);
        if (!t) continue;

        int absIdx = m_rightScroll + i;
        if (absIdx >= total)
        {
            t->SetText("");
            *(INT32*)((BYTE*)t + 0x44) = NH3Dlg::NTextColor::WHITE;
            continue;
        }

        char buf[48];
        snprintf(buf, sizeof(buf), "%d. %s.mp3",
            absIdx + 1,
            ids[absIdx].c_str());
        t->SetText(buf);

        bool active = (ids[absIdx] == activeId && !activeId.empty());
        *(INT32*)((BYTE*)t + 0x44) = active ? NH3Dlg::NTextColor::GOLD : NH3Dlg::NTextColor::WHITE;
    }

    Redraw();
}

// ============================================================================
//  UpdateCenter
// ============================================================================

void PlayerDlg::UpdateCenter()
{
    const Settings& s = g_player.GetSettings();
    std::string audioId = g_player.GetCurrentAudioId();

    if (H3DlgText* t = GetText(ID_TEXT_TIME))
    {
        char cur[12], tot[12], combined[40];
        FormatTime(g_player.current_time, cur, sizeof(cur));
        int d = 0;
        if (!audioId.empty())
            if (const Audio* a = s.FindAudio(audioId))
                d = a->time;
        FormatTime(d, tot, sizeof(tot));
        snprintf(combined, sizeof(combined), "Czas: %s / %s", cur, tot);
        t->SetText(combined);
    }

    if (H3DlgText* t = GetText(ID_TEXT_VOLUME))
    {
        char buf[24];
        snprintf(buf, sizeof(buf), "Vol: %d%%", s.volume / 10);
        t->SetText(buf);
    }

    // Swap DEF przycisku play/paus gdy zmienia się stan odtwarzania
    bool isPlaying = g_player.IsPlaying();
    if (isPlaying != m_wasPlaying)
    {
        m_wasPlaying = isPlaying;
        if (H3DlgDefButton* btn = GetDefButton(ID_BTN_PLAY))
        {
            H3LoadedDef* newDef = H3LoadedDef::Load(isPlaying ? "PAUS_B.def" : "PLAY_B.def");
            if (newDef)
                *(H3LoadedDef**)((BYTE*)btn + 0x30) = newDef;
            btn->SetFrame(0);
            btn->SetClickFrame(1);
        }
    }

    Redraw();
}

// ============================================================================
//  FormatTime
// ============================================================================

void PlayerDlg::FormatTime(int ms, char* buf, size_t len)
{
    if (ms <= 0) { snprintf(buf, len, "0:00"); return; }
    int total_s = ms / 1000;
    snprintf(buf, len, "%d:%02d", total_s / 60, total_s % 60);
}

// ============================================================================
//  Scrollbar callbacks
// ============================================================================

void __fastcall PlayerDlg::VolumeScrollProc(INT32 tick, H3BaseDlg* dlg)
{
    Settings& s = g_player.GetSettings();
    s.volume = tick * 10;
    g_player.ApplyVolume();
    s.Save(g_settingsPath.c_str());

    if (PlayerDlg* pd = static_cast<PlayerDlg*>(dlg))
        pd->UpdateCenter();
}

void __fastcall PlayerDlg::ScrollRightProc(INT32 tick, H3BaseDlg* dlg)
{
    if (PlayerDlg* pd = static_cast<PlayerDlg*>(dlg))
    {
        int total     = (int)g_player.GetSettings().GetCurrentUnlocked().size();
        int maxScroll = (total > N_VISIBLE) ? (total - N_VISIBLE) : 0;
        pd->m_rightScroll = (tick > maxScroll) ? maxScroll : tick;
        pd->UpdateRightList();
    }
}

void __fastcall PlayerDlg::SeekSliderProc(INT32 tick, H3BaseDlg* dlg)
{
    int dur = g_player.GetCurrentDuration();
    if (dur <= 0) return;
    g_player.Seek((int)((INT64)tick * dur / 1000));
}
