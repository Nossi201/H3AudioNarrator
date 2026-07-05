#pragma once

// miniaudio - single-header audio library (MIT license)
// Pobierz: https://raw.githubusercontent.com/mackron/miniaudio/master/miniaudio.h
// Umieść w: external/miniaudio/miniaudio.h
// Implementacja jest w: src/miniaudio_impl.cpp (MINIAUDIO_IMPLEMENTATION)
#include "miniaudio.h"

/**
 * @brief Odtwarzacz MP3 oparty na miniaudio.
 *
 * Zastępuje poprzednią implementację MCI (mciSendStringA).
 * Zachowuje identyczny interfejs publiczny (Player.hpp nie wymaga zmian).
 *
 * Zalety nad MCI:
 *  - Dokładna pozycja odtwarzania w ms (GetPosition)
 *  - Dokładna długość pliku (GetDuration, plik dekodowany w całości)
 *  - Lepsza kontrola głośności (0-1000 → 0.0-1.0 na poziomie silnika)
 *  - Brak zależności od zewnętrznych kodeków systemu
 *  - Każda instancja ma własny silnik i bufor dźwięku
 *
 * Volume: 0-1000 (Settings::volume), konwertowane do 0.0-1.0 dla ma_engine.
 */
class AudioPlayer
{
public:
    enum class State { Stopped, Playing, Paused };

    // -----------------------------------------------------------------------
    AudioPlayer()
        : m_engineInit(false), m_soundLoaded(false), m_state(State::Stopped)
    {
        // ma_engine i ma_sound są inicjalizowane przez ma_engine_init / ma_sound_init_from_file.
        // Flagi m_engineInit / m_soundLoaded chronią przed użyciem niezainicjalizowanych struktur.
    }

    ~AudioPlayer()
    {
        Close();
        if (m_engineInit)
        {
            ma_engine_uninit(&m_engine);
            m_engineInit = false;
        }
    }

    // -----------------------------------------------------------------------
    /**
     * @brief Otwiera plik MP3 do odtwarzania.
     *        Dekoduje plik w całości do RAM (MA_SOUND_FLAG_DECODE)
     *        dla dokładnego GetDuration() i natychmiastowego seekowania.
     */
    bool Open(const char* path)
    {
        Close();

        if (!m_engineInit)
        {
            ma_engine_config cfg = ma_engine_config_init();
            if (ma_engine_init(&cfg, &m_engine) != MA_SUCCESS)
                return false;
            m_engineInit = true;
        }

        // MA_SOUND_FLAG_DECODE: pełny dekod do RAM → dokładna długość, szybki seek
        ma_uint32 flags = MA_SOUND_FLAG_DECODE;
        if (ma_sound_init_from_file(&m_engine, path, flags, NULL, NULL, &m_sound) != MA_SUCCESS)
            return false;

        m_soundLoaded = true;
        m_state       = State::Stopped;
        return true;
    }

    /**
     * @brief Zamyka otwarty plik i zwalnia zasoby dźwięku.
     */
    void Close()
    {
        if (m_soundLoaded)
        {
            ma_sound_stop(&m_sound);
            ma_sound_uninit(&m_sound);
            m_soundLoaded = false;
            m_state       = State::Stopped;
        }
    }

    // -----------------------------------------------------------------------
    /**
     * @brief Odtwarza od początku (seek do 0 + start).
     */
    bool Play()
    {
        if (!m_soundLoaded)
            return false;

        ma_sound_seek_to_pcm_frame(&m_sound, 0);
        if (ma_sound_start(&m_sound) != MA_SUCCESS)
            return false;

        m_state = State::Playing;
        return true;
    }

    /**
     * @brief Zatrzymuje i przewija na początek.
     */
    bool Stop()
    {
        if (!m_soundLoaded)
            return false;

        ma_sound_stop(&m_sound);
        ma_sound_seek_to_pcm_frame(&m_sound, 0);
        m_state = State::Stopped;
        return true;
    }

    /**
     * @brief Wstrzymuje w aktualnej pozycji.
     */
    bool Pause()
    {
        if (!m_soundLoaded || m_state != State::Playing)
            return false;

        ma_sound_stop(&m_sound);  // miniaudio stop nie resetuje pozycji
        m_state = State::Paused;
        return true;
    }

    /**
     * @brief Wznawia z miejsca pauzy.
     */
    bool Resume()
    {
        if (!m_soundLoaded || m_state != State::Paused)
            return false;

        if (ma_sound_start(&m_sound) != MA_SUCCESS)
            return false;

        m_state = State::Playing;
        return true;
    }

    bool TogglePlayPause()
    {
        switch (m_state)
        {
        case State::Stopped: return Play();
        case State::Playing: return Pause();
        case State::Paused:  return Resume();
        }
        return false;
    }

    // -----------------------------------------------------------------------
    State GetState() const { return m_state; }
    bool  IsOpen()   const { return m_soundLoaded; }

    /**
     * @brief Sprawdza czy plik dobiegł końca (aktualizuje stan na Stopped).
     */
    bool IsFinished()
    {
        if (!m_soundLoaded || m_state != State::Playing)
            return false;

        if (ma_sound_at_end(&m_sound))
        {
            m_state = State::Stopped;
            return true;
        }
        return false;
    }

    /**
     * @brief Zwraca aktualną pozycję odtwarzania w milisekundach.
     */
    int GetPosition()
    {
        if (!m_soundLoaded)
            return 0;

        float cursor = 0.0f;
        ma_sound_get_cursor_in_seconds(&m_sound, &cursor);
        return (int)(cursor * 1000.0f);
    }

    /**
     * @brief Zwraca całkowitą długość pliku w milisekundach.
     *        Dostępna od razu dzięki MA_SOUND_FLAG_DECODE.
     */
    int GetDuration()
    {
        if (!m_soundLoaded)
            return 0;

        float length = 0.0f;
        ma_sound_get_length_in_seconds(&m_sound, &length);
        return (int)(length * 1000.0f);
    }

    /**
     * @brief Skacze do podanej pozycji w milisekundach.
     *        Działa natychmiastowo dzięki MA_SOUND_FLAG_DECODE (plik w RAM).
     */
    bool Seek(int ms)
    {
        if (!m_soundLoaded || !m_engineInit)
            return false;

        if (ms < 0) ms = 0;

        ma_uint32 sampleRate = ma_engine_get_sample_rate(&m_engine);
        if (sampleRate == 0) sampleRate = 44100;

        ma_uint64 frame = (ma_uint64)ms * sampleRate / 1000;
        return ma_sound_seek_to_pcm_frame(&m_sound, frame) == MA_SUCCESS;
    }

    /**
     * @brief Ustawia głośność silnika (0-1000 → 0.0-1.0).
     */
    bool SetVolume(int volume)
    {
        if (!m_engineInit)
            return false;

        int   v   = (volume < 0) ? 0 : (volume > 1000) ? 1000 : volume;
        float vol = (float)v / 1000.0f;
        ma_engine_set_volume(&m_engine, vol);
        return true;
    }

private:
    ma_engine   m_engine;
    ma_sound    m_sound;
    bool        m_engineInit;
    bool        m_soundLoaded;
    State       m_state;
};
