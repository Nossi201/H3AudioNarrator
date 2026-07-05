#pragma once

#include "ButtonPlugin.hpp"
#include "Player.hpp"
#include "ToolbarRenderer.hpp"

class PlayerDlg : public h3::H3Dlg
{
public:
    static constexpr INT DLG_W     = 476;
    static constexpr INT DLG_H     = 488;
    static constexpr INT N_VISIBLE = 19;

    // Panel kontrolek (lewy)
    static constexpr INT PC_X  = 21;
    static constexpr INT PC_W  = 240;
    // Panel playlista (prawy): PR_X=263, prawy skraj=DLG_W-21=455
    static constexpr INT PR_X  = 263;
    static constexpr INT PR_W  = 192;

    // IDs – panel kontrolek
    enum : INT32
    {
        ID_TITLE          = 100,
        ID_TEXT_TIME      = 103,
        ID_TEXT_VOLUME    = 104,
        ID_SCROLLBAR_VOL  = 110,
        ID_BTN_PLAY         = 201,
        ID_BTN_RESET        = 203,
        ID_SEEK_SLIDER      = 210,
        ID_BTN_AUTOPLAY     = 211,
        ID_TEXT_AUTOPLAY    = 212,

        // IDs – panel playlista
        ID_TEXT_RIGHT_COUNT = 130,
        ID_SCROLL_RIGHT     = 131,
        ID_BTN_Q_PREV       = 401,
        ID_BTN_Q_NEXT       = 403,
        ID_RIGHT_ITEM_BASE  = 320,
    };

    PlayerDlg();

    BOOL OnCreate() override;
    BOOL OnLeftClick(INT itemId, h3::H3Msg& msg) override;
    BOOL DialogProc(h3::H3Msg& msg) override;

private:
    int         m_rightScroll;
    int         m_lastTick;      // śledzi poprzednią pozycję suwaka seek → redraw tylko gdy zmiana
    std::string m_lastAudioId;   // śledzi poprzednie ID odtwarzanego audio → redraw gdy zmiana
    bool        m_wasPlaying;    // śledzi stan play → swap DEF przycisku play/paus

    void UpdateRightList();
    void UpdateCenter();

    static void FormatTime(int ms, char* buf, size_t len);

    static void __fastcall VolumeScrollProc(INT32 tick, h3::H3BaseDlg* dlg);
    static void __fastcall ScrollRightProc(INT32 tick, h3::H3BaseDlg* dlg);
    static void __fastcall SeekSliderProc(INT32 tick, h3::H3BaseDlg* dlg);
};
