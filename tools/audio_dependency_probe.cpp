// Probe the pinned mixer before integrating its lifetime with the game runtime.
#define SDL_MAIN_HANDLED
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include <SDL3_mixer/SDL_mixer.h>
#include <nlohmann/json.hpp>
#include <array>
#include <cmath>
#include <fstream>
#include <iostream>
#include <stdexcept>

static void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(std::string(message) + ": " + SDL_GetError());
}

int main(int argc, char** argv) {
    MIX_Mixer *mixer=nullptr, *device=nullptr;
    MIX_Audio* audio=nullptr;
    try {
        require(argc==3, "Expected WAV input and JSON output paths");
        SDL_SetMainReady();
        require(SDL_Init(SDL_INIT_AUDIO), "Initialize SDL audio");
        require(MIX_Init(), "Initialize SDL_mixer");
        const SDL_AudioSpec spec{SDL_AUDIO_F32, 2, 48000};
        mixer=MIX_CreateMixer(&spec); require(mixer, "Create offline mixer");
        audio=MIX_LoadAudio(mixer, argv[1], true); require(audio, "Decode fixture WAV");
        require(MIX_GetAudioDuration(audio)==1024, "Decoded duration");
        auto* first=MIX_CreateTrack(mixer); require(first, "Create first track");
        auto* second=MIX_CreateTrack(mixer); require(second, "Create second track");
        require(MIX_SetTrackAudio(first, audio) && MIX_SetTrackAudio(second, audio), "Share audio across tracks");
        nlohmann::json checks=nlohmann::json::array();
        auto check=[&](bool ok, const char* label) { require(ok, label); checks.push_back(label); };
        auto samples=[&](float left, float right) {
            std::array<float,128> pcm{};
            require(MIX_Generate(mixer, pcm.data(), sizeof(pcm))>=0, "Generate PCM");
            for(size_t i=0;i<pcm.size();i+=2)
                require(std::abs(pcm[i]-left)<1e-6f && std::abs(pcm[i+1]-right)<1e-6f, "Unexpected mixed samples");
        };
        require(MIX_PlayTrack(first,0), "Play WAV"); samples(.25f,.125f);
        check(MIX_TrackPlaying(first) && !MIX_TrackPaused(first), "WAV decoding and stereo PCM output");
        auto position=MIX_GetTrackPlaybackPosition(first);
        require(MIX_PauseTrack(first), "Pause"); samples(0,0);
        check(MIX_TrackPaused(first) && !MIX_TrackPlaying(first) && MIX_GetTrackPlaybackPosition(first)==position,
              "Pause produces silence and preserves playback position");
        require(MIX_SetTrackGain(first,.5f) && MIX_ResumeTrack(first), "Change gain and resume"); samples(.125f,.0625f);
        check(MIX_GetTrackPlaybackPosition(first)==position+64, "Resume advances from the paused position with half gain");
        require(MIX_PlayTrack(second,0), "Play second track"); samples(.375f,.1875f);
        check(MIX_TrackPlaying(first) && MIX_TrackPlaying(second), "Independent tracks mix the shared asset additively");
        require(MIX_StopTrack(first,0) && MIX_StopTrack(second,0), "Stop tracks"); samples(0,0);
        check(!MIX_TrackPlaying(first) && !MIX_TrackPaused(first), "Stop produces silence and clears playback state");
        require(MIX_PlayTrack(first,0), "Replay single shot");
        std::array<float,4096> tail{};
        require(MIX_Generate(mixer,tail.data(),sizeof(tail))>=0, "Generate beyond end");
        check(!MIX_TrackPlaying(first) && tail[4095]==0.f, "One-shot playback finishes and appends silence");
        auto options=SDL_CreateProperties(); require(options!=0, "Create loop options");
        require(SDL_SetNumberProperty(options,MIX_PROP_PLAY_LOOPS_NUMBER,-1), "Configure loop");
        const bool looped=MIX_PlayTrack(first,options); SDL_DestroyProperties(options); require(looped, "Loop playback");
        for(int i=0;i<40;++i) samples(.125f,.0625f);
        check(MIX_TrackPlaying(first), "Infinite loop continues through multiple source lengths");
        const char bad[]="not encoded audio";
        auto* invalid=MIX_LoadAudio_IO(mixer,SDL_IOFromConstMem(bad,sizeof(bad)),true,true);
        if(invalid) MIX_DestroyAudio(invalid);
        check(!invalid, "Invalid encoded audio is rejected");
        // Open the default device without any tracks; this does not play a tone.
        device=MIX_CreateMixerDevice(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK,&spec);
        require(device, "Open default playback device");
        check(true, "Default playback device opens");
        nlohmann::json result={{"passed",true},{"mixer_version",MIX_Version()},
            {"audio_driver",SDL_GetCurrentAudioDriver()},{"checks",checks},
            {"scope","Native dependency decoding/mixing and device-open probe; gameplay integration and audible output are not certified"}};
        std::ofstream output(argv[2]); output << result.dump(2) << '\n'; require(bool(output), "Write report");
        MIX_DestroyMixer(device); MIX_DestroyMixer(mixer); MIX_DestroyAudio(audio); MIX_Quit(); SDL_Quit();
        std::cout << result.dump(2) << '\n'; return 0;
    } catch(const std::exception& error) {
        std::cerr << error.what() << '\n';
        if(device) MIX_DestroyMixer(device);
        if(mixer) MIX_DestroyMixer(mixer);
        if(audio) MIX_DestroyAudio(audio);
        MIX_Quit(); SDL_Quit(); return 1;
    }
}
