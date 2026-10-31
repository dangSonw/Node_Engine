#include "runtime.hpp"
#include <SDL3/SDL.h>
#include <atomic>
#include <fstream>
#include <system_error>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#endif

namespace rt {
namespace {
namespace fs = std::filesystem;
constexpr std::size_t MaxSaveBytes = 80 * 1024 * 1024, MaxSlots = 1024;
void Require(bool condition, const char* message) {
    if(!condition) throw std::runtime_error(message);
}
void SlotName(const std::string& slot) {
    Require(!slot.empty() && slot.size() <= 64 && slot.find_first_not_of(' ') != std::string::npos,
            "Save slot must contain 1 to 64 UTF-8 bytes");
    for(unsigned char c : slot) Require(c >= 32 && c != 127, "Save slot cannot contain control characters");
    (void)Json(slot).dump(); // Validate UTF-8 before deriving a filename.
}
std::string Filename(const std::string& slot) {
    SlotName(slot);
    constexpr char hex[] = "0123456789abcdef";
    std::string result = "slot-";
    for(unsigned char c : slot) { result += hex[c >> 4]; result += hex[c & 15]; }
    return result + ".json";
}
std::string SlotFromFilename(const std::string& file) {
    if(!file.starts_with("slot-") || !file.ends_with(".json")) return {};
    const auto hex = file.substr(5, file.size()-10);
    if(hex.empty() || hex.size() > 128 || hex.size()%2) return {};
    auto digit = [](char c) { return c >= '0' && c <= '9' ? c-'0' : c >= 'a' && c <= 'f' ? c-'a'+10 : -1; };
    std::string result;
    for(std::size_t i=0; i<hex.size(); i+=2) {
        const auto a=digit(hex[i]), b=digit(hex[i+1]);
        if(a<0 || b<0) return {};
        result += static_cast<char>((a<<4)|b);
    }
    try { SlotName(result); } catch(const std::exception&) { return {}; }
    return result;
}
bool PlainFile(const fs::path& path) {
    const auto status=fs::symlink_status(path);
    if(status.type()==fs::file_type::not_found) return false;
    Require(fs::is_regular_file(status), "Save path must be a regular file, not a directory or link");
    return true;
}
void Ready(Ctx& c) {
    Require(!c.saves.game.empty(), "Open Save Storage before using save nodes");
    Require(fs::is_directory(fs::symlink_status(c.saves.directory)) &&
            fs::canonical(c.saves.directory)==c.saves.directory, "Save directory changed or is unavailable");
}
void OsError(const char* action) {
#ifdef _WIN32
    throw std::system_error(static_cast<int>(GetLastError()), std::system_category(), action);
#else
    throw std::system_error(errno, std::generic_category(), action);
#endif
}
// One lock covers read/modify/replace across all local game processes. Never
// unlink it: replacing a live lock file could let another process bypass it.
class StorageLock {
#ifdef _WIN32
    HANDLE handle = INVALID_HANDLE_VALUE;
#else
    int handle = -1;
#endif
public:
    explicit StorageLock(const fs::path& directory) {
        const auto path=directory/".storage.lock";
        PlainFile(path);
#ifdef _WIN32
        handle=CreateFileW(path.c_str(), GENERIC_READ|GENERIC_WRITE, 0, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
        if(handle==INVALID_HANDLE_VALUE) OsError("Save storage is busy or cannot be locked");
#else
        handle=open(path.c_str(), O_RDWR|O_CREAT|O_NOFOLLOW|O_CLOEXEC, 0600);
        if(handle<0) OsError("Cannot open save storage lock");
        if(flock(handle, LOCK_EX|LOCK_NB)<0) {
            const auto error=errno; close(handle); handle=-1; errno=error;
            OsError("Save storage is busy");
        }
#endif
    }
    ~StorageLock() {
#ifdef _WIN32
        if(handle!=INVALID_HANDLE_VALUE) CloseHandle(handle);
#else
        if(handle>=0) close(handle);
#endif
    }
    StorageLock(const StorageLock&) = delete;
    StorageLock& operator=(const StorageLock&) = delete;
};
template<class T, class F> T Operation(Ctx& c, T failure, F&& body) {
    c.saves.ok=false; c.saves.error.clear();
    try {
        Ready(c);
        StorageLock lock(c.saves.directory);
        T result=body(); c.saves.ok=true; return result;
    } catch(const std::exception& e) { c.saves.error=e.what(); return failure; }
}
Json Parse(const std::string& text) {
    // nlohmann's parser is iterative, but later tree traversals are recursive.
    // Reject excessive nesting and duplicate keys at this file boundary.
    std::vector<std::set<std::string>> keys;
    return Json::parse(text, [&](int depth, Json::parse_event_t event, Json& value) {
        Require(depth <= 64, "Save JSON nesting exceeds 64 levels");
        if(event==Json::parse_event_t::object_start) keys.emplace_back();
        else if(event==Json::parse_event_t::object_end) keys.pop_back();
        else if(event==Json::parse_event_t::key)
            Require(keys.back().insert(value.get<std::string>()).second, "Duplicate save JSON key");
        return true;
    });
}
Json Empty(const Ctx& c, const std::string& slot) {
    return {{"format","node-engine-save"},{"version",1},{"game_id",c.saves.game},
            {"slot",slot},{"variables",Json::object()},{"json",Json::object()}};
}
std::int64_t Header(const Ctx& c, const std::string& slot, const Json& data) {
    Require(data.is_object() && data.value("format",std::string{})=="node-engine-save", "Not a Node Engine save file");
    Require(data.at("game_id")==c.saves.game && data.at("slot")==slot, "Save game or slot identity mismatch");
    const auto version=FromJson<std::int64_t>(data.at("version"));
    Require(version>0, "Invalid save version");
    return version;
}
void Validate(const Ctx& c, const std::string& slot, const Json& data) {
    const auto version=Header(c,slot,data);
    Require(version==1 || version==2, "Unsupported save version; migration is required");
    Require(data.size()==(version==1 ? 6 : 7) && data.at("variables").is_object() && data.at("json").is_object(), "Invalid save document");
    if(version==1) Require(data.dump().size()<=16*1024*1024,"Version 1 save exceeds 16 MiB");
    else {
        const auto& checkpoint=data.at("checkpoint");
        const bool legacy=checkpoint.is_object()&&checkpoint.value("version",Json())==1;
        // Older whole-game slots remain readable as progress/JSON containers;
        // full restoration separately requires the exact runtime and state schema.
        const bool animation=checkpoint.is_object()&&checkpoint.contains("animation");
        const bool random=checkpoint.is_object()&&checkpoint.contains("random");
        const bool flow=checkpoint.is_object()&&checkpoint.contains("flow");
        const bool continuations=checkpoint.is_object()&&checkpoint.contains("continuations");
        const bool scenes=checkpoint.is_object()&&checkpoint.contains("scene_session");
        Require(checkpoint.is_object() && checkpoint.size()==(legacy?9u:animation?11u:10u)+(random?1u:0u)+(flow?1u:0u)+(continuations?1u:0u)+(scenes?1u:0u) &&
            (!random || (!legacy && animation && checkpoint.at("random").is_object())) &&
            (!flow || (random && checkpoint.at("flow").is_object())) &&
            (!continuations || (flow && checkpoint.at("continuations").is_object())) &&
            (!scenes || (flow && checkpoint.at("scene_session").is_object())) &&
            checkpoint.at("version").is_number_integer() && (legacy||checkpoint.at("version")==2) &&
            checkpoint.at("program").is_object() && checkpoint.at("scene").is_object() && checkpoint.at("identity").is_object() &&
            checkpoint.at("input").is_object() && checkpoint.at("events").is_object() && checkpoint.at("audio").is_object() &&
            checkpoint.at("ui").is_object() && checkpoint.at("clock").is_object() &&
            (legacy || (checkpoint.contains("physics") && (checkpoint.at("physics").is_null() || checkpoint.at("physics").is_object()) &&
                        (!animation || checkpoint.at("animation").is_object()))) &&
            checkpoint.dump().size()<=64*1024*1024,
            "Invalid game checkpoint envelope");
    }
    CollectionSize(data.at("variables").size()); CollectionSize(data.at("json").size());
    for(const auto& [name,value]:data.at("variables").items()) {
        VariableName(name);
        Require(value.is_object() && value.size()==2, "Invalid saved variable");
        (void)ValueFromJson(value.at("type").get<std::string>(),value.at("value"));
    }
    for(const auto& [key,value]:data.at("json").items()) { VariableName(key); StringSize(value.dump().size()); }
}
Json Read(Ctx& c, const std::string& slot, bool missing_ok=false, bool header_only=false) {
    const auto path=c.saves.directory/Filename(slot);
    if(!PlainFile(path)) {
        Require(missing_ok, "Save slot does not exist");
        return Empty(c,slot);
    }
    const auto size=fs::file_size(path);
    Require(size<=MaxSaveBytes, "Save file exceeds 80 MiB");
    std::ifstream file(path, std::ios::binary);
    Require(static_cast<bool>(file), "Cannot read save file");
    std::string text(static_cast<std::size_t>(size),'\0');
    file.read(text.data(),static_cast<std::streamsize>(size));
    Require(file.gcount()==static_cast<std::streamsize>(size) && file.peek()==std::char_traits<char>::eof(), "Save file changed during read");
    auto data=Parse(text);
    if(data.is_object() && data.value("version",Json())==1) Require(size<=16*1024*1024,"Version 1 save exceeds 16 MiB");
    if(header_only) (void)Header(c,slot,data); else Validate(c,slot,data);
    return data;
}
Array<std::string> Slots(const Ctx& c) {
    Array<std::string> result;
    for(const auto& entry:fs::directory_iterator(c.saves.directory)) {
        const auto encoded=entry.path().filename().u8string();
        auto slot=SlotFromFilename(std::string(encoded.begin(),encoded.end()));
        if(slot.empty()) continue;
        Require(result.size()<MaxSlots, "Save storage exceeds 1024 slots");
        result.push_back(std::move(slot)); // Include damaged slots so users can delete them.
    }
    std::sort(result.begin(),result.end());
    return result;
}
void Write(Ctx& c, const std::string& slot, const Json& data) {
    Validate(c,slot,data);
    const auto text=data.dump()+"\n";
    Require(text.size()<=MaxSaveBytes && (data.at("version")!=1 || text.size()<=16*1024*1024), "Save file exceeds its version's size limit");
    (void)Parse(text); // The complete envelope must meet the reader's depth limit.
    const auto path=c.saves.directory/Filename(slot);
    if(!PlainFile(path)) Require(Slots(c).size()<MaxSlots, "At most 1024 save slots are allowed");
    static std::atomic_uint64_t sequence=0;
#ifdef _WIN32
    const auto pid=GetCurrentProcessId();
#else
    const auto pid=getpid();
#endif
    const auto temporary=c.saves.directory/(".write-"+std::to_string(pid)+"-"+std::to_string(++sequence)+".tmp");
    bool owned=false;
    try {
#ifdef _WIN32
        auto file=CreateFileW(temporary.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
        if(file==INVALID_HANDLE_VALUE) OsError("Cannot create temporary save");
        owned=true;
        DWORD written=0;
        const bool success=WriteFile(file,text.data(),static_cast<DWORD>(text.size()),&written,nullptr) && written==text.size() && FlushFileBuffers(file);
        const auto error=GetLastError(); CloseHandle(file);
        if(!success) { SetLastError(error); OsError("Cannot write temporary save"); }
        if(!MoveFileExW(temporary.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)) OsError("Cannot replace save file");
#else
        const auto file=open(temporary.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
        if(file<0) OsError("Cannot create temporary save");
        owned=true;
        std::size_t offset=0;
        while(offset<text.size()) {
            const auto written=write(file,text.data()+offset,text.size()-offset);
            if(written<0 && errno==EINTR) continue;
            if(written<=0) { const auto error=errno; close(file); errno=error; OsError("Cannot write temporary save"); }
            offset+=static_cast<std::size_t>(written);
        }
        if(fsync(file)<0) { const auto error=errno; close(file); errno=error; OsError("Cannot flush temporary save"); }
        if(close(file)<0) OsError("Cannot close temporary save");
        fs::rename(temporary,path);
        const auto directory=open(c.saves.directory.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC);
        if(directory<0) OsError("Cannot flush save directory");
        const auto flushed=fsync(directory), error=errno; close(directory);
        if(flushed<0) { errno=error; OsError("Cannot flush save directory"); }
#endif
        owned=false;
    } catch(...) {
        if(owned) { std::error_code ignored; fs::remove(temporary,ignored); }
        throw;
    }
}
void Names(const Array<std::string>& names) {
    Require(!names.empty(), "Choose at least one variable to save or load");
    CollectionSize(names.size()); std::set<std::string> unique;
    for(const auto& name:names) {
        VariableName(name);
        Require(unique.insert(name).second, "Duplicate variable name");
    }
}
const Value& Variable(const Ctx& c, const std::string& name) {
    return GetVariableValue(c,name);
}
}
bool OpenSaveStorage(Ctx& c, std::string game) {
    c.saves.ok=false; c.saves.error.clear();
    try {
        Require(!game.empty() && game.size()<=64 && game[0]!='-' && game[0]!='_',
                "Game ID must start with a lowercase letter or digit, at most 64 characters");
        for(char ch:game) Require((ch>='a' && ch<='z') || (ch>='0' && ch<='9') || ch=='-' || ch=='_',
                                  "Game ID allows lowercase letters, digits, hyphens and underscores");
        fs::path directory;
        if(c.saves.base.empty()) {
            auto* value=SDL_GetPrefPath("NodeEngine",game.c_str());
            if(!value) throw std::runtime_error(std::string("Cannot find user save directory: ")+SDL_GetError());
            directory=fs::u8path(value); SDL_free(value);
        } else directory=fs::absolute(c.saves.base)/game;
        // Check before canonicalization so an existing linked game folder fails.
        Require(!fs::is_symlink(fs::symlink_status(directory)), "Save directory cannot be a link");
        fs::create_directories(directory);
        directory=fs::canonical(directory);
        StorageLock lock(directory);
        c.saves.directory=std::move(directory); c.saves.game=std::move(game);
        c.saves.ok=true; return true;
    } catch(const std::exception& e) { c.saves.error=e.what(); return false; }
}
bool CreateSaveSlot(Ctx& c,std::string slot) {
    return Operation(c,false,[&] {
        if(PlainFile(c.saves.directory/Filename(slot))) (void)Read(c,slot);
        else Write(c,slot,Empty(c,slot));
        return true;
    });
}
bool DeleteSaveSlot(Ctx& c,std::string slot) {
    return Operation(c,false,[&] {
        const auto path=c.saves.directory/Filename(slot);
        Require(PlainFile(path), "Save slot does not exist");
        Require(fs::remove(path), "Cannot delete save slot"); return true;
    });
}
bool SaveSlotExists(Ctx& c,std::string slot) {
    return Operation(c,false,[&] { return PlainFile(c.saves.directory/Filename(slot)); });
}
Array<std::string> ListSaveSlots(Ctx& c) {
    return Operation(c,Array<std::string>{},[&] { return Slots(c); });
}
bool SaveVariables(Ctx& c,std::string slot,Array<std::string> names) {
    return Operation(c,false,[&] {
        Names(names); auto data=Read(c,slot,true);
        for(const auto& name:names) {
            const auto& value=Variable(c,name);
            std::visit([](const auto& item){CheckValue(item);},value);
            auto serialized=VariableJson(value);
            if(serialized.is_number()) serialized={{"type","float"},{"value",serialized}};
            data["variables"][name]=std::move(serialized);
        }
        Write(c,slot,data); return true;
    });
}
bool LoadVariables(Ctx& c,std::string slot,Array<std::string> names) {
    return Operation(c,false,[&] {
        Names(names); const auto data=Read(c,slot);
        auto variables=c.variables;
        auto globals=c.global_variables;
        auto entities=c.entity_variables;
        for(const auto& name:names) {
            const auto& expected=Variable(c,name);
            Require(data.at("variables").contains(name), "Variable is absent from save slot");
            const auto& saved=data.at("variables").at(name);
            auto value=ValueFromJson(saved.at("type").get<std::string>(),saved.at("value"));
            ValidateStoredUserValue(c,value);
            if(ValueType(value)!=ValueType(expected))
                throw std::runtime_error("Saved variable type mismatch: "+name);
            const auto scope=c.variable_scopes.find(name);
            if(scope!=c.variable_scopes.end() && scope->second=="global") globals[name]=std::move(value);
            else if(scope!=c.variable_scopes.end() && scope->second=="entity") entities[c.self][name]=std::move(value);
            else variables[name]=std::move(value);
        }
        c.variables.swap(variables); c.global_variables.swap(globals); c.entity_variables.swap(entities); return true;
    });
}
bool SaveVariable(Ctx& c,std::string slot,std::string name) { return SaveVariables(c,std::move(slot),{std::move(name)}); }
bool LoadVariable(Ctx& c,std::string slot,std::string name) { return LoadVariables(c,std::move(slot),{std::move(name)}); }
bool SaveJson(Ctx& c,std::string slot,std::string key,std::string text) {
    return Operation(c,false,[&] {
        VariableName(key); StringSize(text.size()); auto value=Parse(text);
        auto data=Read(c,slot,true); data["json"][key]=std::move(value);
        Write(c,slot,data); return true;
    });
}
std::string LoadJson(Ctx& c,std::string slot,std::string key) {
    return Operation(c,std::string{},[&] {
        VariableName(key); const auto data=Read(c,slot);
        Require(data.at("json").contains(key), "JSON key is absent from save slot");
        return data.at("json").at(key).dump();
    });
}
std::int64_t GetSaveVersion(Ctx& c,std::string slot) {
    return Operation(c,std::int64_t{-1},[&] { return Header(c,slot,Read(c,slot,false,true)); });
}
bool ValidateSaveData(Ctx& c,std::string slot) {
    return Operation(c,false,[&] { (void)Read(c,slot); return true; });
}
bool WriteGameCheckpoint(Ctx& c,const std::string& slot,const Json& checkpoint) {
    return Operation(c,false,[&] {
        auto data=Read(c,slot,true); data["version"]=2; data["checkpoint"]=checkpoint;
        Write(c,slot,data); return true;
    });
}
Json ReadGameCheckpoint(Ctx& c,const std::string& slot) {
    return Operation(c,Json(),[&] {
        const auto data=Read(c,slot);
        Require(data.contains("checkpoint"),"Save slot has no game checkpoint"); return data.at("checkpoint");
    });
}
bool SaveOperationSucceeded(Ctx& c) { return c.saves.ok; }
std::string GetSaveError(Ctx& c) { return c.saves.error; }
}
