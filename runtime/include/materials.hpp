#pragma once
#include "values.hpp"
#include <map>
namespace rt {
struct Ctx;
struct MaterialParameters {
    Vec3 color{1};
    double opacity=1, alpha_cutoff=.5;
    std::string alpha_mode="opaque";
    bool unlit=false;
};
struct MaterialBinding {
    std::string asset;
    Json overrides=Json::object();
    bool operator==(const MaterialBinding&) const = default;
};
using MaterialLibrary=std::map<std::string,Json>;
MaterialLibrary ReadMaterialAssets(const Json&);
void MergeMaterialAssets(MaterialLibrary&,const Json&);
void CheckMaterialParameters(const Json&,bool partial=false);
MaterialBinding ReadMaterialBinding(const Json&,const MaterialLibrary&);
Json MaterialBindingJson(const MaterialBinding&);
MaterialParameters ResolveMaterial(const MaterialBinding&,const MaterialLibrary&);
Json MaterialAssets(const Ctx&);
bool MaterialExists(const Ctx&,std::string);
std::string GetMaterial(Ctx&,EntityRef);
void SetMaterial(Ctx&,EntityRef,std::string);
void ClearMaterial(Ctx&,EntityRef);
void ResetMaterialParameters(Ctx&,EntityRef);
Vec3 GetMaterialColor(Ctx&,EntityRef);
void SetMaterialColor(Ctx&,EntityRef,Vec3);
double GetMaterialOpacity(Ctx&,EntityRef);
void SetMaterialOpacity(Ctx&,EntityRef,double);
std::string GetMaterialAlphaMode(Ctx&,EntityRef);
void SetMaterialAlphaMode(Ctx&,EntityRef,std::string);
double GetMaterialAlphaCutoff(Ctx&,EntityRef);
void SetMaterialAlphaCutoff(Ctx&,EntityRef,double);
bool IsMaterialUnlit(Ctx&,EntityRef);
void SetMaterialUnlit(Ctx&,EntityRef,bool);
}
