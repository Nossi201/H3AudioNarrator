#pragma once
#include <Windows.h>
#include <cstdio>
#include <string>

// Sciezka bazowa do plikow audio (format: "...TextDetector\audio\").
// Inicjalizowana w ButtonPlugin::Start() na podstawie lokalizacji DLL.
extern std::string g_audioBasePath;

// code = kompozytowy identyfikator "{kampania}_{lokalneId:03d}" np. "woj_032" -
// to juz jest nazwa pliku bez rozszerzenia, wiec zadnego dodatkowego formatowania.
inline void BuildAudioPath(const std::string& code, char* outPath, size_t maxLen)
{
    snprintf(outPath, maxLen, "%s%s.mp3", g_audioBasePath.c_str(), code.c_str());
}

inline bool AudioExistsForId(const std::string& code)
{
    char path[512];
    BuildAudioPath(code, path, sizeof(path));
    return (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES);
}
