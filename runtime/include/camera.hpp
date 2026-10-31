#pragma once
#include "values.hpp"
#include <glm/mat4x4.hpp>
#include <optional>
namespace rt {
struct Ctx;
struct Camera {
    bool present=false, orthographic=false;
    double fov=60, size=10, near_clip=.1, far_clip=1000;
    bool operator==(const Camera&) const = default;
};
bool HasCamera(const Ctx&,EntityRef);
EntityRef CreateCamera(Ctx&,std::string name,Vec3 position);
EntityRef GetActiveCamera(const Ctx&);
void SetActiveCamera(Ctx&,EntityRef);
void SetCameraPerspective(Ctx&,EntityRef,double fov,double near_clip,double far_clip);
void SetCameraOrthographic(Ctx&,EntityRef,double size,double near_clip,double far_clip);
double GetCameraFOV(Ctx&,EntityRef);
void SetCameraFOV(Ctx&,EntityRef,double);
double GetCameraSize(Ctx&,EntityRef);
void SetCameraSize(Ctx&,EntityRef,double);
void SetCameraClip(Ctx&,EntityRef,double near_clip,double far_clip);
void CameraLookAt(Ctx&,EntityRef,Vec3 target,Vec3 up);
void CameraFollow(Ctx&,EntityRef,EntityRef target,Vec3 offset,double rate);
std::optional<std::pair<glm::mat4,glm::mat4>> GameCameraMatrices(const Ctx&,double aspect);
Vec2 WorldToScreen(const Ctx&,EntityRef camera,Vec3 world,Vec2 viewport);
Vec3 ScreenToWorld(const Ctx&,EntityRef camera,Vec2 screen,double depth,Vec2 viewport);
}
