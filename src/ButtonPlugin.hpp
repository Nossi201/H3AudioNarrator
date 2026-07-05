#pragma once

#include <Plugin.hpp>
#include <H3API.hpp>
#include <fstream>
#include <ctime>
#include <cstdarg>

/**
 * @brief Plugin z systemem logowania do pliku
 */
class ButtonPlugin : public Plugin
{
public:
    ButtonPlugin() : Plugin()
    {
        OpenLog();
        Log("=== H3.ButtonPlugin Start ===");

        Status status = Init("H3.ButtonPlugin");
        if (status == Status::Success)
        {
            Log("Plugin zainicjalizowany pomyslnie");
            Start();
        }
        else
        {
            Log("BLAD: Nie udalo sie zainicjalizowac pluginu");
            ShowError("H3.ButtonPlugin", status);
        }
    }

    ~ButtonPlugin()
    {
        Log("=== H3.ButtonPlugin Stop ===");
        CloseLog();
    }

    static ButtonPlugin& GetPlugin();

    // System logowania
    void OpenLog();
    void CloseLog();
    void Log(const char* message);
    void LogFormat(const char* format, ...);
    void LogAddress(const char* name, _ptr_ address);
    void LogDialog(h3::H3BaseDlg* dlg, const char* context);
    void LogHookContext(HookContext& c, const char* hookName);

private:
    void Start();
    std::ofstream m_logFile;

public:
    // Metody hooków
    int OnGenericHook(HookContext& c, const char* hookName, _ptr_ address);
};