#pragma once

#include "AudioPlayer.hpp"
#include "Settings.hpp"
#include <cstring>
#include <deque>
#include <string>

// Zaimplementowane w ButtonPlugin.cpp (ktore ma juz pelna definicje ButtonPlugin) -
// unika wciagania ButtonPlugin.hpp/Plugin.hpp do tego naglowka, co powodowaloby
// podwojne wlaczenie patcher_x86.hpp (stara i nowa sciezka H3API) w plikach ktore
// juz wlaczaja go bezposrednio (np. ToolbarRenderer.cpp).
void LogAudioStart(const char* fn, const char* audioId, bool autoStart);

class Player
{
public:
    struct QueueItem
    {
        std::string id;
        std::string path;
    };

    int id_Player;
    int current_time;

    // -----------------------------------------------------------------------
    Player()
        : id_Player(0), current_time(0)
    {}

    // -----------------------------------------------------------------------
    bool Play()
    {
        std::string id = m_currentAudioId;
        if (id.empty())
        {
            const std::vector<std::string>& ids = m_settings.GetCurrentUnlocked();
            if (ids.empty()) return false;
            id = ids[0];
        }
        const Audio* audio = m_settings.FindAudio(id);
        if (!audio) return false;
        m_currentAudioId = id;
        return PlayAudio(*audio);
    }

    bool Play(const std::string& audioId)
    {
        const Audio* audio = m_settings.FindAudio(audioId);
        if (!audio) return false;
        m_currentAudioId = audioId;
        // Trzyma selected_audio w synchronizacji z tym co faktycznie gra/zagralo -
        // dzieki temu po pelnym zatrzymaniu (StopAndClose czysci m_currentAudioId,
        // ale NIE selected_audio) kolejny Play trafia we wlasciwe miejsce zamiast
        // wracac do jakiejs starej wartosci sprzed przegladania/PlayNext/PlayPrevious.
        m_settings.selected_audio = audioId;
        return PlayAudio(*audio);
    }

    // Wspolna logika wyboru "co grac gdy uzytkownik nie podal wprost ID": biezacy
    // zaladowany > ostatnio wybrany (selected_audio) > pierwszy odblokowany.
    // Uzywana przez F6 (TogglePlayPause) i pasek (PlaySelectedAudioIfExists),
    // zeby oba interfejsy wybieraly ten sam utwor w tej samej sytuacji.
    bool PlaySelectedOrFirst()
    {
        if (m_settings.GetCurrentUnlocked().empty())
            return false;

        std::string id = m_currentAudioId;
        if (id.empty())
            id = m_settings.selected_audio;
        if (id.empty() || !m_settings.FindAudio(id))
            id = m_settings.GetCurrentUnlocked()[0];

        return Play(id);
    }

    // Kolejkuje audio: jezeli cos gra – dodaje na koniec kolejki; inaczej odpala od razu.
    // Kolejkowanie (czyli obietnica, ze to zagra PO biezacym utworze) respektuje
    // auto_start - gdy Autoplay wylaczony, nowe audio NIE wchodzi do kolejki
    // (zostaje tylko odblokowane/widoczne na liscie, patrz MatchAndMaybePlay).
    bool EnqueuePath(const std::string& audioId, const char* path)
    {
        if (m_audioPlayer.GetState() == AudioPlayer::State::Playing)
        {
            if (!m_settings.auto_start)
                return false;

            QueueItem item;
            item.id   = audioId;
            item.path = path ? path : "";
            m_queue.push_back(item);
            return true;
        }
        return PlayPath(audioId, path);
    }

    bool PlayPath(const std::string& audioId, const char* path)
    {
        if (!m_audioPlayer.Open(path))
            return false;

        m_audioPlayer.SetVolume(m_settings.volume);

        if (!m_audioPlayer.Play())
            return false;

        LogAudioStart("PlayPath", audioId.c_str(), m_settings.auto_start);

        m_currentAudioId = audioId;
        current_time = 0;

        Audio* audio = m_settings.FindAudio(audioId);
        if (audio && audio->time == 0)
            audio->time = m_audioPlayer.GetDuration();

        return true;
    }

    // -----------------------------------------------------------------------
    void Stop()
    {
        if (m_audioPlayer.GetState() == AudioPlayer::State::Playing ||
            m_audioPlayer.GetState() == AudioPlayer::State::Paused)
        {
            current_time = m_audioPlayer.GetPosition();
            m_audioPlayer.Stop();
        }
    }

    void StopAndClose()
    {
        m_audioPlayer.Stop();
        m_audioPlayer.Close();
        current_time = 0;
        m_currentAudioId.clear();
        m_queue.clear();
    }

    // Wstrzymuje bez przewijania na poczatek (AudioPlayer::Pause zachowuje pozycje).
    bool Pause()
    {
        if (m_audioPlayer.GetState() != AudioPlayer::State::Playing)
            return false;
        bool ok = m_audioPlayer.Pause();
        if (ok) current_time = m_audioPlayer.GetPosition();
        return ok;
    }

    // Wznawia z pozycji zapisanej przez Pause().
    bool Resume()
    {
        if (m_audioPlayer.GetState() != AudioPlayer::State::Paused)
            return false;
        return m_audioPlayer.Resume();
    }

    // Przelacznik Graj/Pauza dla przycisku start-stop: kontynuuje od miejsca
    // wstrzymania zamiast zaczynac od nowa. Gdy nic nie jest zaladowane/w pelni
    // zatrzymane, deleguje do PlaySelectedOrFirst() - ta sama logika wyboru co
    // uzywa pasek, zeby F6 i pasek zawsze graly to samo w tej samej sytuacji.
    bool TogglePlayPause()
    {
        if (m_audioPlayer.GetState() == AudioPlayer::State::Playing)
            return Pause();
        if (m_audioPlayer.GetState() == AudioPlayer::State::Paused)
            return Resume();
        return PlaySelectedOrFirst();
    }

    void SeekRelative(int deltaMs)
    {
        if (m_audioPlayer.GetState() == AudioPlayer::State::Stopped)
            return;

        int newPos = current_time + deltaMs;
        int dur    = 0;
        if (const Audio* a = m_settings.FindAudio(m_currentAudioId))
            dur = a->time;

        if (newPos < 0)             newPos = 0;
        if (dur > 0 && newPos > dur) newPos = dur;

        m_audioPlayer.Seek(newPos);
        current_time = newPos;
    }

    // -----------------------------------------------------------------------
    // Przy Autoplay ON odtwarzaja od razu (stare zachowanie); przy OFF tylko
    // przesuwaja zaznaczenie (selected_audio) bez odtwarzania - patrz SelectOrPlay.
    bool PlayNext()
    {
        const std::vector<std::string>& ids = m_settings.GetCurrentUnlocked();
        if (ids.empty()) return false;
        int idx  = FindCurrentIndexInUnlocked();
        int next = (idx + 1) % (int)ids.size();   // idx=-1 → next=0 (pierwszy)
        return SelectOrPlay(ids[next]);
    }

    bool PlayPrevious()
    {
        const std::vector<std::string>& ids = m_settings.GetCurrentUnlocked();
        if (ids.empty()) return false;
        int idx  = FindCurrentIndexInUnlocked();
        int prev = (idx <= 0) ? (int)ids.size() - 1 : idx - 1;  // idx=-1 lub 0 → last
        return SelectOrPlay(ids[prev]);
    }

    // Seek do absolutnej pozycji w ms
    bool Seek(int ms)
    {
        if (ms < 0) ms = 0;
        bool ok = m_audioPlayer.Seek(ms);
        if (ok) current_time = ms;
        return ok;
    }

    int GetCurrentDuration() const
    {
        if (m_currentAudioId.empty()) return 0;
        const Audio* a = m_settings.FindAudio(m_currentAudioId);
        return a ? a->time : 0;
    }

    // Przesuwa element w GetCurrentUnlocked() i zapisuje settings
    void SwapInPlaylist(int idx, int dir, const char* settingsPath)
    {
        std::vector<std::string>& ids = m_settings.GetCurrentUnlocked();
        int newIdx = idx + dir;
        if (idx < 0 || idx >= (int)ids.size()) return;
        if (newIdx < 0 || newIdx >= (int)ids.size()) return;
        std::swap(ids[idx], ids[newIdx]);
        m_settings.Save(settingsPath);
    }

    // -----------------------------------------------------------------------
    void Reset()
    {
        m_audioPlayer.Stop();
        current_time = 0;
        if (m_audioPlayer.IsOpen())
            m_audioPlayer.Play();
    }

    // -----------------------------------------------------------------------
    void Update()
    {
        if (m_audioPlayer.GetState() == AudioPlayer::State::Playing)
        {
            current_time = m_audioPlayer.GetPosition();

            if (m_audioPlayer.IsFinished())
            {
                std::string finishedId = m_currentAudioId;
                m_audioPlayer.Close();
                current_time = 0;
                m_currentAudioId.clear();

                // Kolejka ma pierwszenstwo nad auto_start
                if (!m_queue.empty())
                {
                    QueueItem item = m_queue.front();
                    m_queue.pop_front();
                    PlayPath(item.id, item.path.c_str());
                }
                else if (m_settings.auto_start && !m_settings.GetCurrentUnlocked().empty())
                {
                    // Nie zawijaj playlisty w kolko - po ostatnim utworze zatrzymaj sie
                    // i czekaj na nowe odblokowanie, zamiast wracac do pierwszego.
                    //
                    // UWAGA: nie wolamy tu PlayNext() - ono samo wyznacza "obecny"
                    // indeks przez FindCurrentIndexInUnlocked(), ktora szuka
                    // m_currentAudioId - a to jest juz PUSTE (wyczyszczone wyzej).
                    // Nieznaleziony indeks (-1) + 1 = 0 => PlayNext() zawsze
                    // ladowalby na utwor #0 zamiast na faktycznie nastepny.
                    // Uzywamy wiec juz poprawnie wyliczonego idx (z finishedId,
                    // sprzed czyszczenia) i gramy bezposrednio Play(ids[nextIdx]).
                    const std::vector<std::string>& ids = m_settings.GetCurrentUnlocked();
                    int idx = -1;
                    for (int i = 0; i < (int)ids.size(); i++)
                        if (ids[i] == finishedId) { idx = i; break; }

                    if (idx < 0 || idx + 1 < (int)ids.size())
                    {
                        int nextIdx = (idx < 0) ? 0 : idx + 1;
                        Play(ids[nextIdx]);
                    }
                    // idx to ostatni indeks - koniec playlisty, zatrzymaj sie
                }
            }
        }
    }

    // -----------------------------------------------------------------------
    // Zarzadzanie kolejka
    void RemoveFromQueue(int idx)
    {
        if (idx < 0 || idx >= (int)m_queue.size()) return;
        m_queue.erase(m_queue.begin() + idx);
    }

    // Przesuwa element w kolejce o dir pozycji (+1 nizej, -1 wyzej)
    void MoveInQueue(int idx, int dir)
    {
        int newIdx = idx + dir;
        if (idx < 0 || idx >= (int)m_queue.size()) return;
        if (newIdx < 0 || newIdx >= (int)m_queue.size()) return;
        std::swap(m_queue[idx], m_queue[newIdx]);
    }

    void ClearQueue() { m_queue.clear(); }
    int  GetQueueSize() const { return (int)m_queue.size(); }
    const std::deque<QueueItem>& GetQueue() const { return m_queue; }

    // -----------------------------------------------------------------------
    Settings&           GetSettings()             { return m_settings; }
    const Settings&     GetSettings() const       { return m_settings; }
    const std::string&  GetCurrentAudioId() const { return m_currentAudioId; }
    AudioPlayer::State  GetState() const          { return m_audioPlayer.GetState(); }
    bool                IsPlaying() const         { return m_audioPlayer.GetState() == AudioPlayer::State::Playing; }

    void ApplyVolume()
    {
        if (m_audioPlayer.IsOpen())
            m_audioPlayer.SetVolume(m_settings.volume);
    }

private:
    Settings              m_settings;
    AudioPlayer           m_audioPlayer;
    std::string           m_currentAudioId;
    std::deque<QueueItem> m_queue;

    // Gdy nic aktualnie NIE GRA (auto_start off - tylko przegladanie/zaznaczanie,
    // albo w ogole nic jeszcze nie grało) - cykluj wzgledem ostatnio zaznaczonego
    // (selected_audio), a nie wzgledem m_currentAudioId, ktore zostaje ustawione
    // (i NIE czyszczone) po Pause() - inaczej nawigacja "zamrazalaby sie" na
    // wstrzymanym utworze i nie dalo by sie przejsc dalej samym zaznaczaniem.
    int FindCurrentIndexInUnlocked() const
    {
        const std::vector<std::string>& ids = m_settings.GetCurrentUnlocked();
        const std::string& ref = IsPlaying() ? m_currentAudioId : m_settings.selected_audio;
        for (int i = 0; i < (int)ids.size(); i++)
            if (ids[i] == ref) return i;
        return -1;
    }

    // Przy Autoplay ON odtwarza od razu; przy OFF tylko zaznacza (selected_audio)
    // bez przerywania/zmiany aktualnie zaladowanego audio.
    bool SelectOrPlay(const std::string& id)
    {
        if (m_settings.auto_start)
            return Play(id);
        m_settings.selected_audio = id;
        return true;
    }

    bool PlayAudio(const Audio& audio)
    {
        if (!m_audioPlayer.Open(audio.directory.c_str()))
            return false;

        m_audioPlayer.SetVolume(m_settings.volume);

        if (!m_audioPlayer.Play())
            return false;

        LogAudioStart("PlayAudio", audio.id_Audio.c_str(), m_settings.auto_start);

        current_time = 0;

        Audio* a = m_settings.FindAudio(audio.id_Audio);
        if (a && a->time == 0)
            a->time = m_audioPlayer.GetDuration();

        return true;
    }
};
