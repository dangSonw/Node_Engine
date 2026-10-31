#pragma once
#include "physics_world.hpp"
#include <functional>
#include <map>
#include <tuple>
#include <glm/mat4x4.hpp>

namespace rt {
struct Ctx;
struct PhysicsBinding {
    Vec3 half_extents{.5};
    double radius=.5,half_height=.5;
    std::vector<PhysicsPart> parts;
    bool enabled=true;
    glm::dmat4 observed{1};
};
struct PhysicsScene {
    std::map<std::string,PhysicsBinding> bodies;
    double remainder=0;
    std::uint64_t ticks=0;
};
void SyncPhysics(Ctx&);
PhysicsBody ReadAuthoredBody(const Json&);
void CreateAuthoredBody(Ctx&,EntityRef,const Json&);
void LoadAuthoredPhysics(Ctx&);
void AdvancePhysics(Ctx&);
void ConfigureFixedUpdate(Ctx&,const Json&,std::function<void(Ctx&)> compiled={});
Json PhysicsSnapshot(const Ctx&);
Json PhysicsStateCheckpoint(const Ctx&);
void RestorePhysicsState(Ctx&,const Json&);
void CheckPhysicsClone(Ctx&,EntityRef);
void ClonePhysics(Ctx&,EntityRef source,EntityRef target);
void CreateBoxBody(Ctx&,EntityRef,Vec3,std::string,double,bool,bool);
void CreateSphereBody(Ctx&,EntityRef,double,std::string,double,bool,bool);
void CreateCapsuleBody(Ctx&,EntityRef,double,double,std::string,double,bool,bool);
void RemoveBody(Ctx&,EntityRef);
bool HasBody(Ctx&,EntityRef);
void SetBodyType(Ctx&,EntityRef,std::string);
std::string GetBodyType(Ctx&,EntityRef);
void SetBodyMass(Ctx&,EntityRef,double);
double GetBodyMass(Ctx&,EntityRef);
void SetBodyVelocity(Ctx&,EntityRef,Vec3);
Vec3 GetBodyVelocity(Ctx&,EntityRef);
void SetBodyAngularVelocity(Ctx&,EntityRef,Vec3);
Vec3 GetBodyAngularVelocity(Ctx&,EntityRef);
void ApplyForce(Ctx&,EntityRef,Vec3);
void ApplyImpulse(Ctx&,EntityRef,Vec3);
void ApplyTorque(Ctx&,EntityRef,Vec3);
void SetBodyGravityScale(Ctx&,EntityRef,double);
void SetBodyDamping(Ctx&,EntityRef,double,double);
void WakeBody(Ctx&,EntityRef);
void SleepBody(Ctx&,EntityRef);
bool IsBodyAwake(Ctx&,EntityRef);
void SetBodyEnabled(Ctx&,EntityRef,bool);
bool IsBodyEnabled(Ctx&,EntityRef);
void SetPhysicsMaterial(Ctx&,EntityRef,double,double);
void SetCollisionMask(Ctx&,EntityRef,std::int64_t);
void IgnoreCollisionPair(Ctx&,EntityRef,EntityRef,bool);
void SetPhysicsGravity(Ctx&,Vec3);
EntityRef PhysicsRaycast(Ctx&,Vec3,Vec3,std::int64_t,bool,EntityRef);
using PhysicsQueryResult=std::tuple<bool,EntityRef,Vec3,Vec3,double,double>;
PhysicsQueryResult PhysicsRaycastHit(Ctx&,Vec3,Vec3,std::int64_t,bool,EntityRef);
PhysicsQueryResult PhysicsSphereCast(Ctx&,Vec3,double,Vec3,std::int64_t,bool,EntityRef);
PhysicsQueryResult PhysicsBoxCast(Ctx&,Vec3,Vec3,Vec3,Vec3,std::int64_t,bool,EntityRef);
PhysicsQueryResult PhysicsCapsuleCast(Ctx&,Vec3,double,double,Vec3,Vec3,std::int64_t,bool,EntityRef);
Array<EntityRef> PhysicsOverlapSphere(Ctx&,Vec3,double,std::int64_t,bool,EntityRef);
Array<EntityRef> PhysicsOverlapBox(Ctx&,Vec3,Vec3,Vec3,std::int64_t,bool,EntityRef);
Array<EntityRef> PhysicsOverlapCapsule(Ctx&,Vec3,double,double,Vec3,std::int64_t,bool,EntityRef);
void MoveKinematicBody(Ctx&,EntityRef,Vec3,Vec3,double);
void CreateCharacter(Ctx&,EntityRef,double,double,double,double,double,double,double);
void RemoveCharacter(Ctx&,EntityRef);
bool HasCharacter(Ctx&,EntityRef);
void CharacterMove(Ctx&,EntityRef,Vec3);
bool CharacterJump(Ctx&,EntityRef,double);
bool CharacterResize(Ctx&,EntityRef,double,double);
void ConfigureCharacter(Ctx&,EntityRef,double,double,double,double);
using CharacterGroundResult=std::tuple<bool,std::string,EntityRef,Vec3,Vec3,Vec3>;
CharacterGroundResult CharacterGroundCheck(Ctx&,EntityRef);
}
