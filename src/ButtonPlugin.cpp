#include "ButtonPlugin.hpp"
#include "H3Addresses.hpp"
#include "TextMap.hpp"
#include "AudioLocator.hpp"
#include "ToolbarState.hpp"
#include "ToolbarRenderer.hpp"
#include "ToolbarLayout.hpp"
#include "ToolbarActions.hpp"
#include "Player.hpp"
#include "PlayerDlg.hpp"
#include "h3api/H3Assets/H3LoadedDef.hpp"
#include "h3api/H3Assets/H3Lod.hpp"
#include <string>
#include <ctime>
#include <cstdarg>
#include <cstring>
#include <cctype>

using namespace h3;

// UWAGA: buttonPlugin musi byc zadeklarowany PO wszystkich globalach, ktore
// uzywane sa w jego konstruktorze (przez Start()). W C++ globale w tej samej
// jednostce translacji sa inicjalizowane w kolejnosci deklaracji.
Player       g_player;

// Sciezki inicjalizowane w Start() na podstawie polozenia DLL
std::string g_audioBasePath;
std::string g_textMapPath;
std::string g_settingsPath;

/**
 * @brief Zwraca uchwyt do modulu (DLL), w ktorym ta funkcja sie znajduje.
 *        Dziala bez DllMain - uzywa adresu funkcji jako wskazowki.
 */
static HMODULE GetOwnModuleHandle()
{
    HMODULE hMod = NULL;
    GetModuleHandleExA(
        GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        (LPCSTR)&GetOwnModuleHandle,
        &hMod);
    return hMod;
}

/**
 * @brief Zwraca katalog, w ktorym znajduje sie DLL (ze slashem na koncu).
 *        Np. "C:\\HoMM 3\\_HD3_Data\\Packs\\TextDetector\\"
 */
std::string GetDllDir()
{
    char path[MAX_PATH] = {};
    GetModuleFileNameA(GetOwnModuleHandle(), path, MAX_PATH);
    char* lastSlash = strrchr(path, '\\');
    if (lastSlash) *(lastSlash + 1) = '\0';
    return std::string(path);
}

// buttonPlugin jako OSTATNI global - do tego momentu g_player, g_textMap,
// g_audioBasePath/g_textMapPath/g_settingsPath sa juz skonstruowane.
ButtonPlugin buttonPlugin;

// Wolna funkcja (deklarowana w Player.hpp) zamiast wywolywania buttonPlugin.LogFormat
// bezposrednio z naglowka Player.hpp - patrz komentarz przy deklaracji w Player.hpp.
void LogAudioStart(const char* fn, const char* audioId, bool autoStart)
{
    buttonPlugin.LogFormat("[AudioStart] fn=%s id=%s auto_start=%d",
        fn, audioId, (int)autoStart);
}

//===================================================================================
//                         SYSTEM LOGOWANIA
//===================================================================================

ButtonPlugin& ButtonPlugin::GetPlugin() { return buttonPlugin; }

void ButtonPlugin::OpenLog()
{
    // Zapisz log w katalogu DLL
    std::string logPath = GetDllDir() + "H3ButtonPlugin.log";
    m_logFile.open(logPath.c_str(), std::ios::out | std::ios::trunc);
    if (!m_logFile.is_open())  // fallback
        m_logFile.open("H3ButtonPlugin.log", std::ios::out | std::ios::trunc);
}

void ButtonPlugin::CloseLog()
{
    if (m_logFile.is_open()) { m_logFile.flush(); m_logFile.close(); }
}

void ButtonPlugin::Log(const char* message)
{
    if (m_logFile.is_open())
    {
        time_t now = time(nullptr);
        char timeStr[64];
        strftime(timeStr, sizeof(timeStr), "[%H:%M:%S]", localtime(&now));
        m_logFile << timeStr << " " << message << std::endl;
        m_logFile.flush();
    }
}

void ButtonPlugin::LogFormat(const char* format, ...)
{
    if (m_logFile.is_open())
    {
        char buffer[2048];
        va_list args;
        va_start(args, format);
        vsnprintf(buffer, sizeof(buffer), format, args);
        va_end(args);
        Log(buffer);
    }
}

void ButtonPlugin::LogAddress(const char* name, _ptr_ address) { LogFormat("%s: 0x%08X", name, address); }
void ButtonPlugin::LogDialog(H3BaseDlg* dlg, const char* context) {}
void ButtonPlugin::LogHookContext(HookContext& c, const char* hookName) {}
int  ButtonPlugin::OnGenericHook(HookContext& c, const char* hookName, _ptr_ address) { return EXEC_DEFAULT; }

//===================================================================================
//                    FUNKCJE AUDIO
//===================================================================================

/**
 * @brief Wypelnia g_player.GetSettings().audio_array wszystkimi plikami z dysku.
 *        Odpowiada relacji Settings.audio_array -> Audio z diagramu.
 */
void PopulateAudioArray()
{
    Settings& s = g_player.GetSettings();
    s.audio_array.clear();

    // Iterujemy po juz wczytanym g_textMap (kompozytowe ID "{kampania}_{lokalneId}")
    // zamiast sondowac plaska przestrzen 1-999 - kazda kampania ma wlasny prefiks,
    // wiec nie ma juz jednej wspolnej numeracji do przeiterowania.
    for (const TextMapping& tm : g_textMap)
    {
        if (!AudioExistsForId(tm.id))
            continue;

        char path[512];
        BuildAudioPath(tm.id, path, sizeof(path));

        // Startuje zablokowane - odblokowuje sie przy pierwszym wyswietleniu dialogu
        Audio audio(tm.id, std::string(path), /*locked=*/true, /*mapFilter=*/"");
        s.audio_array.push_back(audio);
    }

    buttonPlugin.LogFormat("PopulateAudioArray: %d plikow audio", (int)s.audio_array.size());
}

//===================================================================================
//                             HOOKS
//===================================================================================

// Osobna funkcja (bez __try) - dopasowanie/odblokowanie/start audio wymaga std::string
// z destruktorem, a __try nie moze wspolistniec z takim obiektem w tej samej ramce
// (ten sam powod co OpenPlayerDlg wyzej). Zwraca true tylko jesli audio ZACZELO GRAC
// NATYCHMIAST (nie gdy zostalo tylko dodane do kolejki) - to steruje czyszczeniem
// po zamknieciu dialogu w HH_MsgDisplay (linger_after_close=false).
static bool MatchAndMaybePlay(LPCSTR text)
{
    buttonPlugin.LogFormat("[MsgDisplay] tekst='%.60s'", text);

    std::string textId = FindTextIdByContent(text);
    if (textId.empty() || !AudioExistsForId(textId))
        return false;

    const char* mapName = GetCurrentMapName();
    buttonPlugin.LogFormat("[MsgDisplay] MATCH ID=%s Map='%s'", textId.c_str(), mapName);

    // Zawsze dodaj do playlisty biezacej mapy
    Settings& settings = g_player.GetSettings();
    settings.SetCurrentMap(mapName);
    if (settings.UnlockAudio(textId))
    {
        settings.Save(g_settingsPath.c_str());
        buttonPlugin.LogFormat("[MsgDisplay] Odblokowano ID=%s", textId.c_str());
    }

    if (!settings.auto_start)
        return false;

    // Nie kolejkuj ponownie tego samego ID, jesli juz gra albo juz czeka w kolejce -
    // HH_MsgDisplay moze sie wywolac wielokrotnie dla tego samego tekstu (np. redraw
    // dialogu), a bez tej ochrony kazde wywolanie dokladaloby kolejna kopie tego
    // samego pliku do kolejki, wiec po zakonczeniu jednego grania lecialby ten sam
    // plik jeszcze raz.
    if (g_player.GetCurrentAudioId() == textId)
        return false;
    for (const auto& item : g_player.GetQueue())
        if (item.id == textId)
            return false;

    char path[512];
    BuildAudioPath(textId, path, sizeof(path));

    // EnqueuePath (nie PlayPath): jesli cos juz gra, nowy tekst dolacza na koniec
    // kolejki i czeka swojej kolejki zamiast przerywac aktualnie odtwarzany plik.
    bool wasPlaying = g_player.IsPlaying();
    bool queuedOrStarted = g_player.EnqueuePath(textId, path);
    bool startedNow = queuedOrStarted && !wasPlaying;

    if (queuedOrStarted)
        buttonPlugin.Log(startedNow ? "[MsgDisplay] Audio start" : "[MsgDisplay] Audio dodane do kolejki (cos juz gra)");

    return startedNow;
}

/**
 * @brief HiHook na 0x4F7D20 (H3Messagebox::display - FASTCALL, 5 args)
 *
 * Przed: wykrywamy tekst i odpalamy audio przez g_player.PlayPath().
 * Po powrocie: zatrzymujemy audio przez g_player.StopAndClose().
 */
void __stdcall HH_MsgDisplay(HiHook* h, LPCSTR text, void* images, int p3, int p4, int timeout)
{
    bool audioStarted = false;

    __try
    {
        if (text)
            audioStarted = MatchAndMaybePlay(text);
    }
    __except(EXCEPTION_EXECUTE_HANDLER)
    {
        buttonPlugin.Log("[MsgDisplay] EXCEPTION!");
    }

    // Wywolaj oryginalna funkcje - BLOKUJE do zamkniecia dialogu
    FASTCALL_5(void, h->GetDefaultFunc(), text, images, p3, p4, timeout);

    // Po zamknieciu dialogu: zatrzymaj audio, chyba ze linger_after_close=true.
    // Tylko gdy TEN dialog faktycznie odpalil audio NATYCHMIAST (nie samo IsPlaying() -
    // od czasu EnqueuePath() cos innego moze grac z zupelnie innego powodu/kolejki,
    // i nie powinnismy tego przerywac ani czyscic kolejki z tego powodu).
    __try
    {
        if (!g_player.GetSettings().linger_after_close && audioStarted)
        {
            g_player.StopAndClose();
            buttonPlugin.Log("[MsgDisplay] Audio cleanup po zamknieciu dialogu");
        }
    }
    __except(EXCEPTION_EXECUTE_HANDLER) {}
}

/**
 * @brief Hook na 0x4F6C00 (H3Messagebox::show - FASTCALL)
 */
// Osobna funkcja (bez __try) - patrz komentarz przy MatchAndMaybePlay.
static void LogMsgShowMatch(LPCSTR text)
{
    std::string textId = FindTextIdByContent(text);
    if (!textId.empty() && AudioExistsForId(textId))
    {
        char path[512];
        BuildAudioPath(textId, path, sizeof(path));
        buttonPlugin.LogFormat("[MsgShow] ID=%s Audio: %s", textId.c_str(), path);
    }
}

_LHF_(LoHook_MsgShow)
{
    __try
    {
        LPCSTR text = (LPCSTR)c->ecx;
        if (text && g_player.GetSettings().auto_start)
            LogMsgShowMatch(text);
    }
    __except(EXCEPTION_EXECUTE_HANDLER) {}

    return EXEC_DEFAULT;
}
static HHOOK         g_keyboardHook  = NULL;
static HHOOK         g_mouseHook     = NULL;
static bool          g_mouseHookOk   = false;
static volatile LONG g_wndOpen       = 0;
static volatile LONG g_openPlayerDlg = 0;

//===================================================================================
//                              PLAYER DIALOG
//===================================================================================

// Osobna funkcja, bo __try/__except nie powinno mieszac sie z obiektami C++
// wymagajacymi destruktorow w tej samej ramce.
static void OpenPlayerDlg()
{
    g_player.GetSettings().SetCurrentMap(GetCurrentMapName());
    buttonPlugin.Log("[Player] Otwieranie PlayerDlg...");
    PlayerDlg playerDlg;
    playerDlg.Start();
    InterlockedExchange(&g_wndOpen, 0L);
    buttonPlugin.Log("[Player] PlayerDlg zamkniety");
}

void SignalOpenPlayerDlg()
{
    if (InterlockedCompareExchange(&g_wndOpen, 1L, 0L) == 0)
        InterlockedExchange(&g_openPlayerDlg, 1L);
}

INT __stdcall HH_DefaultProc(HiHook* h, H3BaseDlg* dlg, H3Msg* msg)
{
    INT result = THISCALL_2(INT, h->GetDefaultFunc(), dlg, msg);

    __try
    {
        // WH_MOUSE_LL jest glowna sciezka dla paska; DefaultProc zostaje tylko fallbackiem,
        // zeby nie dublowac akcji klikniecia.
        if (!g_mouseHookOk)
            HandleToolbarMouse(dlg, msg);
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
    }

    return result;
}

INT __stdcall HH_DlgProc(HiHook* h, H3BaseDlg* dlg, H3Msg* msg)
{
    // Oryginalny DialogProc NAJPIERW - biezaca wiadomosc musi byc w pelni
    // obsluzona zanim ewentualnie zagniezdzimy blokujacy modal OpenPlayerDlg().
    // W przeciwnym razie msg moze zostac odtworzony na nieaktualnym stanie
    // po powrocie z zagniezdzonej petli. (Filtrowanie strzalek na poziomie H3Msg
    // okazalo sie nieskuteczne - patrz KeyboardLLProc, gdzie strzalki sa gaszone
    // na poziomie WH_KEYBOARD_LL, zanim H3Msg w ogole powstanie).
    INT result = THISCALL_2(INT, h->GetDefaultFunc(), dlg, msg);

    __try
    {
        H3AdventureManager* adv = P_AdventureMgr();
        if (adv && adv->dlg && (H3BaseDlg*)adv->dlg == dlg)
        {
            // Regularne wywolanie Update() - obsluguje EOF, pending i playlist
            // nawet gdy PlayerDlg jest zamkniety
            g_player.Update();

            EnsureToolbar((H3AdventureMgrDlg*)adv->dlg);

            if (InterlockedCompareExchange(&g_openPlayerDlg, 0L, 1L) == 1L)
                OpenPlayerDlg();
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        InterlockedExchange(&g_wndOpen, 0L);
        InterlockedExchange(&g_openPlayerDlg, 0L);
    }

    return result;
}

VOID __stdcall HH_H3Redraw(HiHook* h, H3WindowManager* wm, INT32 x, INT32 y, INT32 dx, INT32 dy)
{
    THISCALL_5(VOID, h->GetDefaultFunc(), wm, x, y, dx, dy);

    if (g_toolbar.ready)
    {
        __try
        {
            if (!IsAdventureMapForeground())
            {
                // Opuscilismy mape przygody (np. powrot do menu glownego) -
                // HH_DlgProc juz sie nie odpali zeby to wykryc, bo jest
                // hookiem na DialogProc samej mapy przygody. Gaszymy tu,
                // w hooku ktory odpala sie na kazdym ekranie.
                g_toolbar.ready = false;
                g_toolbar.boundAdventureDlg = nullptr;
            }
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
            g_toolbar.ready = false;
            g_toolbar.boundAdventureDlg = nullptr;
        }
    }

    if (g_toolbar.ready && g_toolbar.absX >= 0 &&
        RectIntersects(x, y, dx, dy, g_toolbar.absX, g_toolbar.absY, g_toolbar.w, g_toolbar.h))
    {
        DrawToolbar(wm, h);
    }
}

//===================================================================================
//                    HOOK KLAWISZOWY F6
//===================================================================================

static LRESULT CALLBACK KeyboardLLProc(int code, WPARAM wParam, LPARAM lParam)
{
    if (code == HC_ACTION)
    {
        KBDLLHOOKSTRUCT* kb = (KBDLLHOOKSTRUCT*)lParam;

        if ((wParam == WM_KEYDOWN || wParam == WM_SYSKEYDOWN) && kb->vkCode == VK_F6)
            SignalOpenPlayerDlg();

        // PlayerDlg (F6) blokuje watek gry w natywnym modalu (H3Dlg::Start).
        // Strzalki docierajace do gry w tym stanie koncza sie access violation
        // w HD_SOD.dll/_hd3_.dll (scroll mapy HD). Filtrowanie na poziomie H3Msg/
        // DialogProc nie dzialalo - HD przechwytuje strzalki przed H3Msg, wiec
        // gasimy je tu, na najnizszym poziomie (surowy komunikat OS), zanim
        // dotrze do kogokolwiek w procesie.
        if (g_wndOpen &&
            (kb->vkCode == VK_LEFT || kb->vkCode == VK_RIGHT ||
             kb->vkCode == VK_UP   || kb->vkCode == VK_DOWN))
        {
            return 1;
        }
    }

    return CallNextHookEx(g_keyboardHook, code, wParam, lParam);
}

// Low-level mouse hook: zachowuje dzialanie przyciskow niezaleznie od tego,
// czy H3 DefaultProc odda prawidlowy item/msg dla naszego paska.
// To ma dzialac jak w poprzedniej wersji: LMB down = stan pressed,
// LMB up na tym samym przycisku = akcja.
static LRESULT CALLBACK MouseLLProc(int code, WPARAM wParam, LPARAM lParam)
{
    if (code == HC_ACTION && (wParam == WM_LBUTTONDOWN || wParam == WM_LBUTTONUP))
    {
        __try
        {
            HWND hwnd = *(HWND*)(H3Addr::H3_HWND_PTR);
            if (hwnd && g_toolbar.ready)
            {
                MSLLHOOKSTRUCT* ms = (MSLLHOOKSTRUCT*)lParam;
                POINT pt = ms->pt;
                ScreenToClient(hwnd, &pt);

                const INT hit = HitToolbarButton((INT)pt.x, (INT)pt.y);

                if (wParam == WM_LBUTTONDOWN)
                {
                    bool changed = false;
                    EnterCriticalSection(&g_toolbar.cs);
                    for (INT i = 0; i < TOOLBAR_BTN_COUNT; i++)
                    {
                        const bool newPressed = (i == hit);
                        if (g_toolbar.btns[i].pressed != newPressed)
                        {
                            g_toolbar.btns[i].pressed = newPressed;
                            changed = true;
                        }
                    }
                    LeaveCriticalSection(&g_toolbar.cs);
                    if (changed)
                        RequestRedrawToolbarRegion();
                }
                else if (wParam == WM_LBUTTONUP)
                {
                    INT pressed = -1;
                    EnterCriticalSection(&g_toolbar.cs);
                    for (INT i = 0; i < TOOLBAR_BTN_COUNT; i++)
                        if (g_toolbar.btns[i].pressed)
                            pressed = i;
                    LeaveCriticalSection(&g_toolbar.cs);

                    ClearToolbarPressed();

                    if (pressed >= 0 && pressed == hit)
                        ExecuteToolbarAction(g_toolbar.btns[pressed].kind);
                }
            }
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
        }
    }

    return CallNextHookEx(g_mouseHook, code, wParam, lParam);
}

static DWORD WINAPI HookThreadProc(LPVOID)
{
    g_keyboardHook = SetWindowsHookEx(WH_KEYBOARD_LL, KeyboardLLProc, NULL, 0);
    if (!g_keyboardHook)
    {
        buttonPlugin.LogFormat("[HookThread] SetWindowsHookEx KBD FAILED: %d", (int)GetLastError());
        return 1;
    }

    buttonPlugin.Log("[HookThread] WH_KEYBOARD_LL zainstalowany");

    g_mouseHook = SetWindowsHookEx(WH_MOUSE_LL, MouseLLProc, NULL, 0);
    if (!g_mouseHook)
    {
        g_mouseHookOk = false;
        buttonPlugin.LogFormat("[HookThread] SetWindowsHookEx MOUSE FAILED: %d", (int)GetLastError());
    }
    else
    {
        g_mouseHookOk = true;
        buttonPlugin.Log("[HookThread] WH_MOUSE_LL zainstalowany");
    }

    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0))
    {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    if (g_mouseHook)
    {
        UnhookWindowsHookEx(g_mouseHook);
        g_mouseHook = NULL;
        g_mouseHookOk = false;
    }

    if (g_keyboardHook)
    {
        UnhookWindowsHookEx(g_keyboardHook);
        g_keyboardHook = NULL;
    }

    return 0;
}

//===================================================================================
//                             START
//===================================================================================

void ButtonPlugin::Start()
{
    Log("=== H3.ButtonPlugin Start ===");

    std::string dllDir  = GetDllDir();
    g_audioBasePath = dllDir + "audio\\";
    g_textMapPath   = dllDir + "text_map.txt";
    g_settingsPath  = dllDir + "H3ButtonPlugin.ini";

    LogFormat("DLL dir: %s", dllDir.c_str());

    Settings& s = g_player.GetSettings();
    if (s.Load(g_settingsPath.c_str()))
        Log("Ustawienia wczytane z H3ButtonPlugin.ini");
    else
        Log("Brak H3ButtonPlugin.ini - uzywam wartosci domyslnych");

    LogFormat("  volume=%d  auto_start=%d  selected_audio=%s",
              s.volume, (int)s.auto_start, s.selected_audio.c_str());

    TextMap_SetLog([](const char* msg) { buttonPlugin.Log(msg); });
    int mapCount = LoadTextMap(g_textMapPath.c_str());
    LogFormat("Mapowania: %d, Sciezka: %s", mapCount, g_textMapPath.c_str());

    PopulateAudioArray();
    int audioCount = (int)g_player.GetSettings().audio_array.size();

    s.ApplyUnlockState();
    int unlockedCount = 0;
    for (const auto& kv : s.unlocked_per_map)
        unlockedCount += (int)kv.second.size();
    LogFormat("Audio: %d plikow, %d odblokowanych lacznie", audioCount, unlockedCount);

    s.Save(g_settingsPath.c_str());

    Hook(H3Addr::MSG_DISPLAY, HType::Splice, HConvention::Fastcall, HH_MsgDisplay);
    LogFormat("HiHook 0x%X (MsgDisplay) zainstalowany", H3Addr::MSG_DISPLAY);

    Hook(H3Addr::MSG_SHOW, LoHook_MsgShow);
    LogFormat("Hook 0x%X (MsgShow) zainstalowany", H3Addr::MSG_SHOW);

    Hook(H3Addr::DLG_PROC, HType::Splice, HConvention::Thiscall, HH_DlgProc);
    LogFormat("HiHook 0x%X (DlgProc) zainstalowany", H3Addr::DLG_PROC);

    Hook(H3Addr::DEFAULT_PROC, HType::Splice, HConvention::Thiscall, HH_DefaultProc);
    LogFormat("HiHook 0x%X (DefaultProc) zainstalowany", H3Addr::DEFAULT_PROC);

    Hook(H3Addr::H3_REDRAW, HType::Splice, HConvention::Thiscall, HH_H3Redraw);
    LogFormat("HiHook 0x%X (H3Redraw) zainstalowany", H3Addr::H3_REDRAW);

    HANDLE hHookThread = CreateThread(NULL, 0, HookThreadProc, NULL, 0, NULL);
    if (hHookThread)
    {
        CloseHandle(hHookThread);
        Log("Hook thread uruchomiony (F6 + mouse toolbar)");
    }
    else
    {
        LogFormat("BLAD: CreateThread hook = %d", (int)GetLastError());
    }

    char msg[256];
    snprintf(msg, sizeof(msg),
        "H3.ButtonPlugin zaladowany!\n"
        "Mapowania: %d | Audio: %d | Volume: %d\n"
        "[F6] = Odtwarzacz | [Przycisk na mapie] = Odtwarzacz",
        mapCount, audioCount, s.volume);

    MessageBoxA(nullptr, msg, "H3.ButtonPlugin", MB_OK | MB_ICONINFORMATION);
}
