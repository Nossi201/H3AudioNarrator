#include "ToolbarActions.hpp"
#include "ToolbarRenderer.hpp"
#include "ToolbarLayout.hpp"
#include "AudioLocator.hpp"
#include "Player.hpp"
#include "Settings.hpp"
#include <H3API.hpp>
#include <string>

using namespace h3;

extern Player g_player;

// Zdefiniowana w ButtonPlugin.cpp — sygnalizuje otwarcie PlayerDlg z wątku gry
extern void SignalOpenPlayerDlg();

//===================================================================================
//                              AKCJE TOOLBARA
//===================================================================================

void ClearToolbarPressed()
{
    bool changed = false;
    g_toolbar.SafeClearAllPressed(&changed);
    if (changed)
        RequestRedrawToolbarRegion();
}

// Cienki wrapper: Player::PlaySelectedOrFirst() to ta sama logika wyboru, ktorej
// uzywa F6 (Player::TogglePlayPause()) - oba interfejsy graja to samo w tej samej
// sytuacji. Tu dochodzi tylko zachowanie specyficzne dla paska (otworz F6 gdy
// nic nie jest jeszcze odblokowane).
static void PlaySelectedAudioIfExists()
{
    if (g_player.GetSettings().GetCurrentUnlocked().empty())
    {
        SignalOpenPlayerDlg();
        return;
    }

    g_player.PlaySelectedOrFirst();
    RequestRedrawToolbarRegion();
}

// Next/Previous zawsze natychmiast przelacza i gra, niezaleznie od stanu
// Playing/Paused/Stopped - tak samo jak [<<]/[>>] w F6 (PlayNext/PlayPrevious
// juz same aktualizuja selected_audio przez Player::Play()).
static void SelectRelativeAudio(int dir)
{
    if (dir > 0) g_player.PlayNext();
    else         g_player.PlayPrevious();

    RequestRedrawToolbarRegion();
}

void ExecuteToolbarAction(ToolbarButtonKind kind)
{
    switch (kind)
    {
    case TB_PREVIOUS:
        SelectRelativeAudio(-1);
        break;

    case TB_NEXT:
        SelectRelativeAudio(+1);
        break;

    case TB_PLAYPAUSE:
        // Pauza/wznowienie zachowuje pozycje (kontynuacja), nie restartuje od 0.
        // StopAndClose() zostaje zarezerwowany dla prawdziwego zatrzymania
        // (np. po zamknieciu dialogu kampanii w HH_MsgDisplay).
        if (g_player.IsPlaying())
            g_player.Pause();
        else if (g_player.GetState() == AudioPlayer::State::Paused)
            g_player.Resume();
        else
            PlaySelectedAudioIfExists();
        RequestRedrawToolbarRegion();
        break;

    case TB_MENU:
        SignalOpenPlayerDlg();
        break;
    }
}

//===================================================================================
//                            OBSŁUGA MYSZY (FALLBACK)
//===================================================================================

void HandleToolbarMouse(H3BaseDlg* dlg, H3Msg* msg)
{
    if (!msg || !g_toolbar.ready)
        return;

    H3AdventureManager* adv = P_AdventureMgr();
    if (!adv || !adv->dlg || (H3BaseDlg*)adv->dlg != dlg)
        return;

    const int cmd = msg->command;
    const int sub = msg->subtype;
    const int mx  = msg->GetX();
    const int my  = msg->GetY();
    const int hit = HitToolbarButton(mx, my);

    if (cmd == 0x0200 && sub == 0x000C) // LMB down
    {
        EnterCriticalSection(&g_toolbar.cs);
        for (int i = 0; i < TOOLBAR_BTN_COUNT; i++)
            g_toolbar.btns[i].pressed = (i == hit);
        LeaveCriticalSection(&g_toolbar.cs);
        RequestRedrawToolbarRegion();
    }
    else if (cmd == 0x0200 && sub == 0x000D) // LMB release/click
    {
        int pressed = -1;
        EnterCriticalSection(&g_toolbar.cs);
        for (int i = 0; i < TOOLBAR_BTN_COUNT; i++)
            if (g_toolbar.btns[i].pressed)
                pressed = i;
        LeaveCriticalSection(&g_toolbar.cs);

        ClearToolbarPressed();

        if (pressed >= 0 && pressed == hit)
            ExecuteToolbarAction(g_toolbar.btns[pressed].kind);
    }
    else if (cmd == 0x0200 && sub == 0x000E) // RMB
    {
        ClearToolbarPressed();
    }
    else
    {
        RequestRedrawToolbarRegion();
    }
}
