#include "sprites.hpp"
#include <regex>
#include <filesystem>
namespace rt {
namespace {
void require(bool value,const char* message) { if(!value) throw std::runtime_error(message); }
}
SpriteLibrary ReadSpriteAssets(const Json& values) {
    require(values.is_array() && values.size()<=1024,"At most 1024 sprite assets are allowed");
    static const std::regex identifier("[A-Za-z0-9_-]{1,48}");
    SpriteLibrary result;
    for(const auto& value:values) {
        require(value.is_object() && value.size()==11,"Invalid sprite asset fields");
        require(value.at("version").is_number_integer() && value.at("version")==1 && value.at("type")=="sprite","Unsupported sprite version/type");
        auto id=value.at("id").get<std::string>(), name=value.at("name").get<std::string>();
        require(std::regex_match(id,identifier) && !result.contains(id),"Invalid or duplicate sprite ID");
        CheckValue(name);
        require(!name.empty() && name.size()<=512 && name.find_first_not_of(" \t\r\n")!=std::string::npos &&
            std::none_of(name.begin(),name.end(),[](unsigned char c){return c<32 || c==127;}),"Invalid sprite name");
        auto texture=value.at("texture").get<std::string>(); CheckValue(texture);
        require(texture.size()<=4096 && texture.starts_with("assets/") && texture.find_first_of("\\:")==std::string::npos &&
            std::none_of(texture.begin(),texture.end(),[](unsigned char c){return c<32 || c==127;}),"Sprite texture must be inside project assets");
        auto path=std::filesystem::u8path(texture);
        const auto normalized=path.lexically_normal().generic_u8string();
        require(std::string(normalized.begin(),normalized.end())==texture,"Sprite texture requires a normalized relative path");
        for(const auto& part:path) require(part!="..","Sprite texture escapes assets");
        auto ext=path.extension().string(); std::transform(ext.begin(),ext.end(),ext.begin(),[](unsigned char c){return std::tolower(c);});
        require(ext==".png" || ext==".jpg" || ext==".jpeg","Sprite texture must be PNG or JPEG");
        for(const auto* key:{"columns","rows"}) require(value.at(key).is_number_integer() && value.at(key)>=1 && value.at(key)<=8192,"Invalid sprite grid");
        require(value.at("columns").get<int>()*value.at("rows").get<int>()<=65536,"At most 65536 sprite frames are allowed");
        for(const auto* key:{"width","height"}) { const auto n=FromJson<double>(value.at(key)); require(n>0 && n<=1e6,"Invalid sprite dimensions"); }
        const auto& pivot=value.at("pivot"); require(pivot.is_array() && pivot.size()==2,"Invalid sprite pivot");
        for(const auto& v:pivot) { const auto n=FromJson<double>(v); require(n>=0 && n<=1,"Invalid sprite pivot"); }
        require(value.at("filter")=="nearest" || value.at("filter")=="linear","Invalid sprite filter");
        result.emplace(id,value);
    }
    return result;
}
void MergeSpriteAssets(SpriteLibrary& library,const Json& values) {
    for(const auto& [id,value]:ReadSpriteAssets(values)) {
        require(!library.contains(id) || library.at(id)==value,"Conflicting sprite asset"); library[id]=value;
    }
    require(library.size()<=1024,"At most 1024 sprite assets are allowed");
}
SpriteBinding ReadSpriteBinding(const Json& value,const SpriteLibrary& library) {
    if(value.is_null()) return {};
    require(value.is_object() && value.size()==4,"Invalid sprite binding fields");
    auto id=value.at("asset").get<std::string>(); require(library.contains(id),"Sprite binding references an unknown asset");
    const auto& asset=library.at(id);
    require(value.at("frame").is_number_integer() && value.at("frame")>=0 &&
        value.at("frame")<asset.at("columns").get<int>()*asset.at("rows").get<int>(),"Sprite frame is outside its atlas");
    require(value.at("flip_x").is_boolean() && value.at("flip_y").is_boolean(),"Sprite flips must be boolean");
    return {id,value.at("frame").get<std::int64_t>(),value.at("flip_x").get<bool>(),value.at("flip_y").get<bool>()};
}
Json SpriteBindingJson(const SpriteBinding& binding) {
    if(binding.asset.empty()) return nullptr;
    return {{"asset",binding.asset},{"frame",binding.frame},{"flip_x",binding.flip_x},{"flip_y",binding.flip_y}};
}
}
