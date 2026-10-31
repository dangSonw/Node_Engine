#pragma once
#include "values.hpp"
namespace rt {
struct Ctx;
using SpriteLibrary = std::map<std::string,Json>;
struct SpriteBinding {
    std::string asset;
    std::int64_t frame=0;
    bool flip_x=false, flip_y=false;
    bool operator==(const SpriteBinding&) const = default;
};
SpriteLibrary ReadSpriteAssets(const Json&);
void MergeSpriteAssets(SpriteLibrary&,const Json&);
SpriteBinding ReadSpriteBinding(const Json&,const SpriteLibrary&);
Json SpriteBindingJson(const SpriteBinding&);
Json SpriteAssets(const Ctx&);
bool SpriteExists(const Ctx&,std::string);
void SetSprite(Ctx&,EntityRef,std::string);
void ClearSprite(Ctx&,EntityRef);
std::string GetSprite(Ctx&,EntityRef);
void SetSpriteFrame(Ctx&,EntityRef,std::int64_t);
std::int64_t GetSpriteFrame(Ctx&,EntityRef);
std::int64_t GetSpriteFrameCount(Ctx&,EntityRef);
void SetSpriteFlip(Ctx&,EntityRef,bool,bool);
bool GetSpriteFlipX(Ctx&,EntityRef);
bool GetSpriteFlipY(Ctx&,EntityRef);
}
