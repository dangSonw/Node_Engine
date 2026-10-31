#include "materials.hpp"
#include <algorithm>
#include <cmath>
#include <regex>
#include <set>
namespace rt {
namespace {
const std::set<std::string> fields={"color","opacity","alpha_mode","alpha_cutoff","unlit"};
void require(bool value,const char* message) { if(!value) throw std::runtime_error(message); }
void unit(double value) { require(std::isfinite(value) && value>=0 && value<=1,"Material values must be between 0 and 1"); }
}
void CheckMaterialParameters(const Json& value,bool partial) {
    require(value.is_object() && (partial || value.size()==fields.size()),"Invalid material parameter fields");
    for(const auto& [key,v]:value.items()) {
        require(fields.contains(key),"Unknown material parameter");
        if(key=="color") { auto color=vec_from_json(v); unit(color.x); unit(color.y); unit(color.z); }
        else if(key=="opacity" || key=="alpha_cutoff") unit(FromJson<double>(v));
        else if(key=="alpha_mode") require(v=="opaque" || v=="mask" || v=="blend","Invalid material alpha mode");
        else require(v.is_boolean(),"Material unlit must be boolean");
    }
}
MaterialLibrary ReadMaterialAssets(const Json& values) {
    require(values.is_array() && values.size()<=1024,"At most 1024 material assets are allowed");
    static const std::regex identifier("[A-Za-z0-9_-]{1,48}");
    MaterialLibrary library;
    for(const auto& value:values) {
        require(value.is_object() && value.size()==fields.size()+4,"Invalid material asset fields");
        require(value.at("version").is_number_integer() && value.at("version")==1 && value.at("type")=="material","Unsupported material version/type");
        const auto id=value.at("id").get<std::string>(),name=value.at("name").get<std::string>();
        require(std::regex_match(id,identifier) && !library.contains(id),"Invalid or duplicate material ID");
        CheckValue(name);
        require(!name.empty() && name.size()<=512 && name.find_first_not_of(" \t\r\n")!=std::string::npos &&
            std::none_of(name.begin(),name.end(),[](unsigned char c){return c<32 || c==127;}),"Invalid material name");
        auto parameters=value;
        for(const auto* key:{"version","type","id","name"}) parameters.erase(key);
        CheckMaterialParameters(parameters);
        library.emplace(id,value);
    }
    return library;
}
void MergeMaterialAssets(MaterialLibrary& library,const Json& values) {
    for(const auto& [id,value]:ReadMaterialAssets(values)) {
        require(!library.contains(id) || library.at(id)==value,"Conflicting material asset");
        library[id]=value;
    }
    require(library.size()<=1024,"At most 1024 material assets are allowed");
}
MaterialBinding ReadMaterialBinding(const Json& value,const MaterialLibrary& library) {
    if(value.is_null()) return {};
    require(value.is_object() && value.size()==2 && value.contains("asset") && value.contains("overrides"),"Material binding requires asset and overrides");
    auto asset=value.at("asset").get<std::string>();
    require(library.contains(asset),"Material binding references an unknown asset");
    CheckMaterialParameters(value.at("overrides"),true);
    return {asset,value.at("overrides")};
}
Json MaterialBindingJson(const MaterialBinding& value) {
    if(value.asset.empty()) return nullptr;
    return {{"asset",value.asset},{"overrides",value.overrides}};
}
MaterialParameters ResolveMaterial(const MaterialBinding& binding,const MaterialLibrary& library) {
    require(!binding.asset.empty(),"Entity has no assigned material");
    auto value=library.at(binding.asset);
    value.update(binding.overrides);
    return {vec_from_json(value.at("color")),FromJson<double>(value.at("opacity")),
        FromJson<double>(value.at("alpha_cutoff")),value.at("alpha_mode").get<std::string>(),value.at("unlit").get<bool>()};
}
}
