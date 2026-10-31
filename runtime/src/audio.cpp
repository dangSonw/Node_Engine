#include "runtime.hpp"
#include <SDL3/SDL.h>
#include <SDL3_mixer/SDL_mixer.h>
#include <array>
#include <fstream>
#include <regex>

namespace rt {
namespace {
constexpr SDL_AudioSpec format{SDL_AUDIO_F32,2,48000};
constexpr size_t checkpoint_operations=65536;
constexpr uint64_t checkpoint_frames=48000ull*3600,checkpoint_calls=1080000;
void check(bool ok,const std::string& message) { if(!ok) throw std::runtime_error(message); }
void sdl(bool ok,const char* message) { if(!ok) throw std::runtime_error(std::string(message)+": "+SDL_GetError()); }
void name(const std::string& text) {
    check(!text.empty() && text.size()<=128 && text.find_first_not_of(" \t\r\n")!=std::string::npos &&
        std::none_of(text.begin(),text.end(),[](unsigned char c){return c<32 || c==127;}),"Invalid sound voice name");
}
void gain(double v) { check(std::isfinite(v) && v>=0 && v<=1,"Audio volume must be between 0 and 1"); }
std::filesystem::path utf8(const std::string& s) { return std::filesystem::path(std::u8string(s.begin(),s.end())); }
void word(std::ostream& out,uint32_t value,int bytes) {
    for(int i=0;i<bytes;++i) out.put(static_cast<char>((value>>(8*i))&255));
}
void header(std::ostream& out,uint32_t bytes) {
    out.seekp(0); out.write("RIFF",4); word(out,bytes+36,4); out.write("WAVEfmt ",8);
    word(out,16,4); word(out,3,2); word(out,2,2); word(out,48000,4); word(out,48000*8,4);
    word(out,8,2); word(out,32,2); out.write("data",4); word(out,bytes,4);
}
struct Sound {
    MIX_Audio* data=nullptr;
    int frequency=0;
    Sint64 frames=0;
    ~Sound() { if(data) MIX_DestroyAudio(data); }
};
struct Voice {
    MIX_Track* track=nullptr;
    std::string sound;
    bool loop=false;
    double volume=1;
    uint64_t serial=0,mixed_frames=0;
    ~Voice() { if(track) MIX_DestroyTrack(track); }
};
}
struct AudioSystem {
    Json assets=Json::array();
    std::map<std::string,std::unique_ptr<Sound>> sounds;
    std::map<std::string,std::unique_ptr<Voice>> voices;
    MIX_Mixer* mixer=nullptr;
    SDL_AudioStream* output=nullptr;
    bool initialized=false,device_initialized=false,prepared=false;
    double master=1,fraction=0;
    uint64_t frames=0,serial=0;
    Json history=Json::array();
    uint64_t history_frames=0,history_calls=0;
    bool history_complete=true,reconstructing=false;
    std::ofstream capture;
    uint32_t captured_bytes=0;
    void finish() {
        if(!capture.is_open()) return;
        header(capture,captured_bytes); capture.flush();
        const bool ok=bool(capture); capture.close();
        check(ok,"Cannot finish audio capture");
    }
    ~AudioSystem() {
        try { finish(); } catch(...) {}
        if(output) SDL_DestroyAudioStream(output);
        voices.clear(); sounds.clear();
        if(mixer) MIX_DestroyMixer(mixer);
        if(initialized) MIX_Quit();
        if(device_initialized) SDL_QuitSubSystem(SDL_INIT_AUDIO);
    }
};
static AudioSystem& system(const Ctx& c) {
    if(!c.audio) throw std::runtime_error("Audio scene is not initialized");
    return *c.audio;
}
static void record(AudioSystem& a,Json operation) {
    if(a.reconstructing || !a.history_complete) return;
    if(operation[0]=="mix") {
        const auto frames=operation[1].get<uint64_t>();
        if(frames>checkpoint_frames-a.history_frames || a.history_calls==checkpoint_calls) {
            a.history_complete=false; a.history.clear(); return;
        }
        a.history_frames+=frames; ++a.history_calls;
        if(!a.history.empty() && a.history.back()[0]=="mix" && a.history.back()[1]==frames) {
            auto& count=a.history.back()[2]; count=count.get<uint64_t>()+1; return;
        }
    }
    // shortcut: bound exact decoder replay; replace with seekable converted assets
    // before exposing unrestricted long-session Save Game support.
    if(a.history.size()==checkpoint_operations) { a.history_complete=false; a.history.clear(); return; }
    a.history.push_back(std::move(operation));
}
std::shared_ptr<AudioSystem> CreateAudioSystem(const Json& values) {
    check(values.is_array() && values.size()<=1024,"At most 1024 sound assets are allowed");
    std::set<std::string> ids;
    static const std::regex identifier("[A-Za-z0-9_-]{1,48}");
    for(const auto& a:values) {
        check(a.is_object() && a.size()==5,"Invalid sound asset fields");
        check(a.at("version").is_number_integer() && a.at("version")==1 && a.at("type")=="sound","Unsupported sound version/type");
        const auto id=a.at("id").get<std::string>();
        check(std::regex_match(id,identifier) && ids.insert(id).second,"Invalid or duplicate sound ID");
        const auto label=a.at("name").get<std::string>();
        check(!label.empty() && label.size()<=512 && label.find_first_not_of(" \t\r\n")!=std::string::npos &&
            std::none_of(label.begin(),label.end(),[](unsigned char c){return c<32 || c==127;}),"Invalid sound name");
        const auto file=a.at("file").get<std::string>();
        check(file.starts_with("assets/") && file.size()<=4096 && file.find_first_of("\\:")==std::string::npos &&
            std::none_of(file.begin(),file.end(),[](unsigned char c){return c<32 || c==127;}),"Sound file must be inside project assets");
        const auto path=utf8(file); const auto normalized=path.lexically_normal().generic_u8string();
        check(std::string(normalized.begin(),normalized.end())==file,"Sound file requires a normalized relative path");
        for(const auto& part:path) check(part!="..","Sound file escapes project assets");
        auto ext=path.extension().string(); std::transform(ext.begin(),ext.end(),ext.begin(),[](unsigned char c){return std::tolower(c);});
        check(ext==".wav" || ext==".ogg" || ext==".mp3" || ext==".flac","Sound requires WAV, Ogg, MP3 or FLAC");
    }
    auto result=std::make_shared<AudioSystem>(); result->assets=values; return result;
}
void PrepareAudio(Ctx& c,const std::filesystem::path& root,bool playback) {
    auto& a=system(c); check(!a.prepared,"Audio is already prepared");
    if(a.assets.empty()) { a.prepared=true; return; }
    sdl(MIX_Init(),"Initialize SDL_mixer"); a.initialized=true;
    a.mixer=MIX_CreateMixer(&format); sdl(a.mixer,"Create audio mixer");
    const auto base=std::filesystem::canonical(root);
    check(std::filesystem::canonical(base/"assets")==base/"assets","Sound assets directory escapes project");
    size_t total=0;
    for(const auto& asset:a.assets) {
        const auto path=std::filesystem::canonical(base/utf8(asset.at("file").get<std::string>()));
        const auto relative=path.lexically_relative(base/"assets");
        check(!relative.empty() && !relative.is_absolute(),"Sound file escapes project assets");
        for(const auto& p:relative) check(p!="..","Sound file escapes project assets");
        const auto size=std::filesystem::file_size(path); total+=size;
        check(size>0 && size<=64*1024*1024 && total<=256*1024*1024,"Sound files exceed 64 MiB each / 256 MiB per scene");
        std::vector<char> bytes(size); std::ifstream file(path,std::ios::binary);
        check(bool(file.read(bytes.data(),static_cast<std::streamsize>(size))),"Cannot read sound file");
        auto sound=std::make_unique<Sound>();
        const auto options=SDL_CreateProperties();
        auto* io=SDL_IOFromConstMem(bytes.data(),bytes.size());
        // The node's Loop input controls repetition, including files with embedded loop points.
        const bool configured=options && io &&
            SDL_SetPointerProperty(options,MIX_PROP_AUDIO_LOAD_IOSTREAM_POINTER,io) &&
            SDL_SetBooleanProperty(options,MIX_PROP_AUDIO_LOAD_CLOSEIO_BOOLEAN,false) &&
            SDL_SetBooleanProperty(options,MIX_PROP_AUDIO_LOAD_PREDECODE_BOOLEAN,false) &&
            SDL_SetPointerProperty(options,MIX_PROP_AUDIO_LOAD_PREFERRED_MIXER_POINTER,a.mixer) &&
            SDL_SetBooleanProperty(options,MIX_PROP_AUDIO_LOAD_IGNORE_LOOPS_BOOLEAN,true);
        sound->data=configured ? MIX_LoadAudioWithProperties(options) : nullptr;
        const std::string error=sound->data ? "" : SDL_GetError();
        if(io) SDL_CloseIO(io);
        SDL_DestroyProperties(options);
        check(sound->data,"Decode sound asset: "+error);
        SDL_AudioSpec source{}; sdl(MIX_GetAudioFormat(sound->data,&source),"Read sound format");
        sound->frequency=source.freq; sound->frames=MIX_GetAudioDuration(sound->data);
        check(source.freq>0 && source.freq<=384000 && source.channels>0 && source.channels<=8 &&
            sound->frames>0 && sound->frames<=Sint64(source.freq)*3600,"Sound must have a known positive duration up to one hour");
        a.sounds.emplace(asset.at("id").get<std::string>(),std::move(sound));
    }
    a.prepared=true;
    if(playback) EnableAudioOutput(c);
}
void EnableAudioOutput(Ctx& c) {
    auto& a=system(c); check(a.prepared,"Sound assets are not loaded");
    if(a.assets.empty() || a.output) return;
    sdl(SDL_InitSubSystem(SDL_INIT_AUDIO),"Initialize playback device"); a.device_initialized=true;
    a.output=SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK,&format,nullptr,nullptr);
    sdl(a.output,"Open playback stream");
}
static Sound& sound(Ctx& c,const std::string& id) {
    auto& a=system(c); check(a.prepared,"Sound assets are not loaded");
    auto it=a.sounds.find(id); check(it!=a.sounds.end(),"Unknown sound asset: "+id); return *it->second;
}
static Voice& voice(Ctx& c,const std::string& id) {
    name(id); auto& voices=system(c).voices; const auto it=voices.find(id);
    check(it!=voices.end(),"Unknown sound voice: "+id); return *it->second;
}
void PlaySound(Ctx& c,std::string id,std::string channel,bool loop,double volume) {
    name(channel); gain(volume); auto& source=sound(c,id); auto& a=system(c);
    check(a.voices.contains(channel) || a.voices.size()<256,"At most 256 sound voices are allowed");
    check(a.serial<std::numeric_limits<uint64_t>::max(),"Sound voice sequence exhausted");
    auto next=std::make_unique<Voice>(); next->sound=id; next->loop=loop; next->volume=volume;
    next->track=MIX_CreateTrack(a.mixer); sdl(next->track,"Create sound voice");
    sdl(MIX_SetTrackAudio(next->track,source.data),"Assign sound");
    sdl(MIX_SetTrackGain(next->track,static_cast<float>(volume)),"Set sound volume");
    const auto options=SDL_CreateProperties(); sdl(options!=0,"Create playback options");
    const bool configured=SDL_SetNumberProperty(options,MIX_PROP_PLAY_LOOPS_NUMBER,loop ? -1 : 0);
    const bool played=configured && MIX_PlayTrack(next->track,options); SDL_DestroyProperties(options);
    sdl(played,"Play sound"); next->serial=++a.serial; a.voices.insert_or_assign(channel,std::move(next));
    record(a,{"play",id,channel,loop,volume});
}
void StopSound(Ctx& c,std::string id) { sdl(MIX_StopTrack(voice(c,id).track,0),"Stop sound"); record(system(c),{"stop",id}); }
void PauseSound(Ctx& c,std::string id) { sdl(MIX_PauseTrack(voice(c,id).track),"Pause sound"); record(system(c),{"pause",id}); }
void ResumeSound(Ctx& c,std::string id) { sdl(MIX_ResumeTrack(voice(c,id).track),"Resume sound"); record(system(c),{"resume",id}); }
bool IsSoundPlaying(Ctx& c,std::string id) { name(id); return system(c).voices.contains(id) && MIX_TrackPlaying(voice(c,id).track); }
bool IsSoundPaused(Ctx& c,std::string id) { name(id); return system(c).voices.contains(id) && MIX_TrackPaused(voice(c,id).track); }
void SetSoundVolume(Ctx& c,std::string id,double v) { gain(v); auto& t=voice(c,id); sdl(MIX_SetTrackGain(t.track,static_cast<float>(v)),"Set sound volume"); t.volume=v; record(system(c),{"gain",id,v}); }
double GetSoundVolume(Ctx& c,std::string id) { return voice(c,id).volume; }
double GetSoundPosition(Ctx& c,std::string id) { auto& t=voice(c,id); return double(MIX_GetTrackPlaybackPosition(t.track))/sound(c,t.sound).frequency; }
double GetSoundDuration(Ctx& c,std::string id) { auto& s=sound(c,id); return double(s.frames)/s.frequency; }
bool SoundExists(Ctx& c,std::string id) { const auto& a=system(c).assets; return std::any_of(a.begin(),a.end(),[&](const auto& v){return v.at("id")==id;}); }
void StopAllSounds(Ctx& c) { for(const auto& [id,_]:system(c).voices) StopSound(c,id); }
void SetMasterVolume(Ctx& c,double v) { gain(v); system(c).master=v; }
double GetMasterVolume(Ctx& c) { return system(c).master; }
void PauseAudioOutput(Ctx& c,bool paused) {
    auto& a=system(c); if(!a.output) return;
    sdl(paused ? SDL_PauseAudioStreamDevice(a.output) : SDL_ResumeAudioStreamDevice(a.output),"Change audio playback state");
}
void BeginAudioCapture(Ctx& c,const std::filesystem::path& path) {
    auto& a=system(c); a.finish(); a.capture.open(path,std::ios::binary|std::ios::trunc); a.captured_bytes=0;
    check(bool(a.capture),"Cannot open audio capture"); header(a.capture,0);
}
void FinishAudioCapture(Ctx& c) { system(c).finish(); }
static void mix(AudioSystem& a,float* pcm,uint64_t count) {
    for(const auto& [_,v]:a.voices) if(MIX_TrackPlaying(v->track)) v->mixed_frames+=count;
    if(a.mixer) sdl(MIX_Generate(a.mixer,pcm,static_cast<int>(count*8))>=0,"Mix audio");
    record(a,{"mix",count,1});
}
void AdvanceAudio(Ctx& c) {
    AdvanceAudio(c,c.dt);
}
void AdvanceAudio(Ctx& c,double seconds) {
    auto& a=system(c);
    if(a.assets.empty() && !a.capture.is_open()) return;
    check(std::isfinite(seconds) && seconds>=0 && seconds<=60,"Audio timestep must be between 0 and 60 seconds");
    const auto exact=seconds*48000+a.fraction;
    auto remaining=static_cast<uint64_t>(std::floor(exact+1e-9)); a.fraction=exact-remaining;
    check(remaining<=std::numeric_limits<uint64_t>::max()-a.frames,"Audio sample counter exhausted");
    if(a.capture.is_open()) check(uint64_t(a.captured_bytes)+remaining*8<=1024ull*1024*1024,"Audio capture exceeds 1 GiB");
    while(remaining) {
        const auto count=std::min<uint64_t>(remaining,2048); std::array<float,4096> pcm{};
        const int bytes=static_cast<int>(count*8);
        mix(a,pcm.data(),count);
        for(size_t i=0;i<count*2;++i) pcm[i]=std::clamp(pcm[i]*static_cast<float>(a.master),-1.f,1.f);
        if(a.capture.is_open()) { a.capture.write(reinterpret_cast<const char*>(pcm.data()),bytes); check(bool(a.capture),"Cannot write audio capture"); a.captured_bytes+=bytes; }
        if(a.output) {
            // Keep latency bounded after a device stall; gameplay/mixer time remains authoritative.
            if(SDL_GetAudioStreamQueued(a.output)>48000*8/4) sdl(SDL_ClearAudioStream(a.output),"Clear stalled audio stream");
            sdl(SDL_PutAudioStreamData(a.output,pcm.data(),bytes),"Queue audio");
        }
        a.frames+=count; remaining-=count;
    }
}
Json AudioAssets(const Ctx& c) { return system(c).assets; }
Json AudioOutputStatus(const Ctx& c) {
    const auto& a=system(c);
    if(!a.output) return {{"connected",false}};
    return {{"connected",true},{"driver",SDL_GetCurrentAudioDriver()},
        {"paused",SDL_AudioDevicePaused(SDL_GetAudioStreamDevice(a.output))},
        {"queued_bytes",SDL_GetAudioStreamQueued(a.output)}};
}
void TransferAudioOutput(Ctx& source,Ctx& candidate) {
    auto& old=system(source); auto& next=system(candidate);
    check(&old!=&next && old.prepared && next.prepared && (!old.output || (!next.output && !next.device_initialized)) && !next.capture.is_open(),
        "Audio handoff requires an independent prepared candidate without host resources");
    if(old.output) sdl(SDL_ClearAudioStream(old.output),"Discard audio queued before game restoration");
    // All fallible preparation precedes these resource swaps.
    next.capture.swap(old.capture); std::swap(next.captured_bytes,old.captured_bytes);
    if(old.output) {std::swap(next.output,old.output); std::swap(next.device_initialized,old.device_initialized);}
}
Json AudioSnapshot(const Ctx& c) {
    const auto& a=system(c); if(a.assets.empty() && a.voices.empty() && a.master==1) return nullptr;
    Json voices=Json::object();
    for(const auto& [id,t]:a.voices) voices[id]={{"sound",t->sound},{"loop",t->loop},{"volume",t->volume},
        {"playing",MIX_TrackPlaying(t->track)},{"paused",MIX_TrackPaused(t->track)},
        {"position_frames",MIX_GetTrackPlaybackPosition(t->track)}};
    return {{"master_volume",a.master},{"sample_frames",a.frames},{"voices",voices}};
}
Json AudioCheckpoint(const Ctx& c) {
    const auto& a=system(c);
    check(a.history_complete,"Audio checkpoint replay budget exceeded; reset the scene before saving");
    Json voices=Json::object();
    for(const auto& [id,t]:a.voices) voices[id]={{"sound",t->sound},{"loop",t->loop},{"volume",t->volume},
        {"playing",MIX_TrackPlaying(t->track)},{"paused",MIX_TrackPaused(t->track)},
        {"position_frames",MIX_GetTrackPlaybackPosition(t->track)},{"serial",t->serial},{"mixed_frames",t->mixed_frames}};
    return {{"version",2},{"assets",a.assets},{"master_volume",a.master},{"sample_frames",a.frames},
        {"fraction",a.fraction},{"serial",a.serial},{"voices",voices},{"history",a.history}};
}
void RestoreAudioCheckpoint(Ctx& c,const Json& saved,const std::filesystem::path& root,bool playback) {
    check(saved.is_object() && saved.size()==8 && saved.contains("version") &&
        saved.at("version").is_number_integer() && saved.at("version")==2,"Invalid audio checkpoint/version");
    check(saved.at("assets")==AudioAssets(c),"Audio checkpoint asset library mismatch");
    auto number=[](const Json& v) {
        check(v.is_number_integer() && (v.is_number_unsigned() || v.get<int64_t>()>=0),"Invalid audio checkpoint counter");
        return v.get<uint64_t>();
    };
    const auto frames=number(saved.at("sample_frames")),serial=number(saved.at("serial"));
    const auto fraction=FromJson<double>(saved.at("fraction")),master=FromJson<double>(saved.at("master_volume"));
    check(fraction>=-1e-9 && fraction<1,"Invalid audio sample fraction"); gain(master);
    const auto& voices=saved.at("voices");
    check(voices.is_object() && voices.size()<=256,"Invalid audio checkpoint voices");
    std::map<uint64_t,std::string> order;
    for(const auto& [id,t]:voices.items()) {
        name(id);
        check(t.is_object() && t.size()==8,"Invalid audio checkpoint voice fields");
        const auto sequence=number(t.at("serial"));
        check(sequence>0 && sequence<=serial && order.emplace(sequence,id).second,"Invalid audio voice sequence");
        check(t.at("sound").is_string() && t.at("loop").is_boolean() && t.at("playing").is_boolean() &&
            t.at("paused").is_boolean() && !(t.at("playing").get<bool>() && t.at("paused").get<bool>()),"Invalid audio voice state");
        gain(FromJson<double>(t.at("volume")));
        check(number(t.at("position_frames"))<=uint64_t(INT64_MAX),"Invalid sound position");
        check(number(t.at("mixed_frames"))<=frames,"Sound elapsed samples exceed mixer clock");
    }
    const auto& history=saved.at("history");
    check(history.is_array() && history.size()<=checkpoint_operations && history.dump().size()<=16*1024*1024,
        "Invalid audio checkpoint history size");
    uint64_t replay_frames=0,replay_calls=0;
    std::set<std::string> names;
    for(const auto& op:history) {
        check(op.is_array() && !op.empty() && op[0].is_string(),"Invalid audio checkpoint operation");
        const auto kind=op[0].get<std::string>();
        if(kind=="mix") {
            check(op.size()==3,"Invalid audio checkpoint mix fields");
            const auto count=number(op[1]),repeat=number(op[2]);
            check(count>0 && count<=2048 && repeat>0 && repeat<=(checkpoint_frames-replay_frames)/count &&
                repeat<=checkpoint_calls-replay_calls,"Audio checkpoint replay budget exceeded");
            replay_frames+=count*repeat; replay_calls+=repeat;
        } else if(kind=="play") {
            check(op.size()==5 && op[1].is_string() && op[2].is_string() && op[3].is_boolean(),"Invalid audio checkpoint play fields");
            const auto id=op[2].get<std::string>(); name(id); names.insert(id); gain(FromJson<double>(op[4]));
            check(SoundExists(c,op[1].get<std::string>()) && names.size()<=256,"Invalid audio checkpoint asset or voice");
        } else {
            check((kind=="gain" && op.size()==3) || ((kind=="stop" || kind=="pause" || kind=="resume") && op.size()==2),
                "Invalid audio checkpoint control fields");
            check(op[1].is_string() && names.contains(op[1].get<std::string>()),"Audio checkpoint controls an unknown voice");
            if(kind=="gain") gain(FromJson<double>(op[2]));
        }
    }
    check(replay_frames==frames,"Audio checkpoint history disagrees with mixer clock");
    Ctx next; next.audio=CreateAudioSystem(saved.at("assets")); PrepareAudio(next,root,playback);
    auto& a=system(next); a.reconstructing=true;
    // Exact call sizes and intervening controls matter: SDL's resampler retains
    // buffered samples even on paused tracks. Replaying elapsed totals loses them.
    for(const auto& op:history) {
        const auto kind=op[0].get<std::string>();
        if(kind=="mix") {
            std::array<float,4096> discard{};
            for(uint64_t i=0;i<op[2].get<uint64_t>();++i) mix(a,discard.data(),op[1].get<uint64_t>());
        } else if(kind=="play") PlaySound(next,op[1].get<std::string>(),op[2].get<std::string>(),op[3].get<bool>(),op[4].get<double>());
        else if(kind=="stop") StopSound(next,op[1].get<std::string>());
        else if(kind=="pause") PauseSound(next,op[1].get<std::string>());
        else if(kind=="resume") ResumeSound(next,op[1].get<std::string>());
        else SetSoundVolume(next,op[1].get<std::string>(),op[2].get<double>());
    }
    a.reconstructing=false; a.history=history; a.history_frames=replay_frames; a.history_calls=replay_calls;
    a.master=master; a.fraction=fraction; a.frames=frames;
    check(AudioCheckpoint(next)==saved,"Audio checkpoint history disagrees with voice state");
    c.audio=std::move(next.audio);
}
}
