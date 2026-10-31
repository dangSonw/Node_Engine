#include "runtime.hpp"
#include "../third_party/picosha2/picosha2.hpp"
#include <SDL3/SDL.h>
#include <SDL3_mixer/SDL_mixer.h>
#include <array>
#include <cctype>
#include <fstream>
#include <set>

namespace rt {
namespace {
namespace fs=std::filesystem;
void require(bool ok,const char* message) { if(!ok) throw std::runtime_error(message); }
std::string text(const fs::path& path) { const auto s=path.generic_u8string(); return {s.begin(),s.end()}; }
fs::path local_file(const fs::path& root,const fs::path& relative) {
    require(!relative.empty() && !relative.is_absolute() && !relative.has_root_name(),"Checkpoint resource must be relative");
    const auto path=(root/relative).lexically_normal(),local=path.lexically_relative(root);
    require(!local.empty() && *local.begin()!="..","Checkpoint resource escapes its directory");
    auto part=root;
    for(const auto& name:local) {
        part/=name;
        require(!fs::is_symlink(fs::symlink_status(part)) && fs::canonical(part)==part,"Checkpoint resource cannot be a link");
    }
    require(fs::is_regular_file(path),"Checkpoint resource must be a regular file");
    return path;
}
Json model_document(const fs::path& path) {
    const auto size=fs::file_size(path); require(size<=64*1024*1024,"Checkpoint model exceeds 64 MiB");
    std::ifstream input(path,std::ios::binary); require(bool(input),"Cannot read checkpoint model");
    auto extension=path.extension().string();
    for(auto& c:extension) c=char(std::tolower(static_cast<unsigned char>(c)));
    uint64_t length=size;
    if(extension==".glb") {
        auto word=[&]() {
            std::array<unsigned char,4> bytes{};
            require(bool(input.read(reinterpret_cast<char*>(bytes.data()),4)),"Truncated checkpoint GLB header");
            return uint32_t(bytes[0]) | uint32_t(bytes[1])<<8 | uint32_t(bytes[2])<<16 | uint32_t(bytes[3])<<24;
        };
        require(word()==0x46546c67 && word()==2 && word()==size,"Invalid checkpoint GLB header");
        length=word(); require(word()==0x4e4f534a && size>=20 && length<=size-20,"Invalid checkpoint GLB JSON chunk");
    } else require(extension==".gltf","Checkpoint model must be glTF or GLB");
    std::string bytes(length,'\0'); require(bool(input.read(bytes.data(),length)),"Cannot read checkpoint model JSON");
    auto doc=Json::parse(bytes);
    require(doc.is_object() && doc.contains("asset") && doc.at("asset").value("version",std::string{})=="2.0","Expected checkpoint glTF 2.0 document");
    return doc;
}
fs::path dependency_path(const std::string& uri) {
    require(uri.find_first_of(":?#\\") == std::string::npos,"Checkpoint model dependency must be a relative local file");
    std::string decoded;
    auto hex=[](char c) { if(c>='0'&&c<='9') return c-'0'; if(c>='a'&&c<='f') return c-'a'+10; if(c>='A'&&c<='F') return c-'A'+10; return -1; };
    for(size_t i=0;i<uri.size();++i) {
        auto c=uri[i];
        if(c=='%') {
            require(i+2<uri.size() && hex(uri[i+1])>=0 && hex(uri[i+2])>=0,"Invalid checkpoint dependency URI escape");
            c=char(hex(uri[i+1])*16+hex(uri[i+2])); i+=2;
        }
        require(c!='\0' && c!='\\' && c!=':',"Invalid checkpoint dependency path"); decoded+=c;
    }
    return fs::u8path(decoded);
}
Json file_identity(const fs::path& path) {
    const auto size=fs::file_size(path);
    require(size<=1024ull*1024*1024,"Checkpoint resource exceeds 1 GiB");
    std::ifstream input(path,std::ios::binary); require(bool(input),"Cannot read checkpoint resource");
    picosha2::hash256_one_by_one hash; std::array<char,65536> buffer{}; uint64_t read=0;
    while(input) {
        input.read(buffer.data(),buffer.size()); const auto count=input.gcount();
        read+=count; require(read<=size,"Checkpoint resource changed during hashing");
        hash.process(buffer.begin(),buffer.begin()+count);
    }
    require(input.eof() && read==size && fs::file_size(path)==size,"Cannot read stable checkpoint resource");
    hash.finish(); return {{"bytes",size},{"sha256",picosha2::get_hash_hex_string(hash)}};
}
}
Json GameProgramIdentity(const Json& program,const fs::path& root) {
    require(program.is_object() && ((program.contains("scene") && program.contains("events")) ||
            (program.contains("scenes") && program.at("scenes").is_object())),"Invalid checkpoint program");
    const auto encoded=program.dump(); require(encoded.size()<=8*1024*1024,"Checkpoint program exceeds 8 MiB");
    Json files=Json::object(); const auto project=fs::canonical(root),assets=project/"assets";
    uint64_t total=0;
    auto add=[&](const fs::path& path) {
        const auto key=text(path.lexically_relative(project)); if(files.contains(key)) return;
        require(files.size()<4096,"Checkpoint assets require at most 4096 regular files");
        const auto size=fs::file_size(path); require(size<=1024ull*1024*1024-total,"Checkpoint resource library exceeds 1 GiB");
        total+=size; files[key]=file_identity(path);
    };
    if(fs::exists(assets)) {
        require(fs::is_directory(fs::symlink_status(assets)) && fs::canonical(assets)==assets,"Checkpoint assets directory cannot be a link");
        for(const auto& entry:fs::recursive_directory_iterator(assets)) {
            const auto status=entry.symlink_status();
            require(!fs::is_symlink(status) && fs::canonical(entry.path())==entry.path(),"Checkpoint resource cannot be a link");
            if(fs::is_directory(status)) continue;
            require(fs::is_regular_file(status) && files.size()<4096,"Checkpoint assets require at most 4096 regular files");
            add(entry.path());
        }
    }
    std::set<std::string> meshes;
    auto collect=[&](const Json& scene) {
        for(const auto& entity:scene.value("entities",Json::array())) {
            const auto mesh=entity.value("mesh",std::string{}); if(!mesh.empty()) meshes.insert(mesh);
        }
    };
    bool uses_ui=false;
    auto collect_scene=[&](const Json& scene) {
        collect(scene); for(const auto& prefab:scene.value("prefab_templates",Json::array())) collect(prefab);
        uses_ui=uses_ui || !scene.value("ui_assets",Json::array()).empty();
    };
    if(program.contains("scenes")) for(const auto& p:program.at("scenes")) collect_scene(p.at("scene"));
    else collect_scene(program.at("scene"));
    for(const auto& mesh:meshes) {
        require(mesh.find_first_of(":\\") == std::string::npos && mesh.find('\0')==std::string::npos,"Invalid checkpoint model path");
        const auto model=local_file(project,fs::u8path(mesh)); add(model);
        // The full assets tree is already hashed; its loaders enforce local dependencies.
        if(*model.lexically_relative(project).begin()=="assets") continue;
        const auto doc=model_document(model);
        for(const auto* group:{"buffers","images"}) {
            const auto entries=doc.value(group,Json::array()); require(entries.is_array(),"Invalid checkpoint model dependencies");
            for(const auto& item:entries) {
                const auto uri=item.value("uri",std::string{});
                if(uri.empty() || uri.starts_with("data:")) continue;
                add(local_file(model.parent_path(),dependency_path(uri)));
            }
        }
    }
    Json result={{"version",1},{"runtime",NODE_ENGINE_CHECKPOINT_ABI},{"program_sha256",picosha2::hash256_hex_string(encoded)},
        {"platform",SDL_GetPlatform()},{"pointer_bytes",sizeof(void*)},{"sdl",SDL_GetVersion()},{"mixer",MIX_Version()},{"assets",files}};
    if(uses_ui)
        result["font"]=file_identity(fs::u8path(SDL_GetBasePath())/"fonts/RobotoMono-Regular.ttf");
    return result;
}
}
