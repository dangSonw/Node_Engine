#pragma once
#include "values.hpp"
#include <glm/gtc/quaternion.hpp>
#include <memory>
#include <array>
#include <vector>

namespace rt {
struct PhysicsPart {
    std::string shape="box";
    Vec3 position{0}, half_extents{.5};
    glm::dquat rotation{1,0,0,0};
    double radius=.5, half_height=.5;
    std::vector<Vec3> vertices;
    std::vector<std::array<std::uint32_t,3>> triangles;
    bool operator==(const PhysicsPart&) const = default;
};
struct PhysicsBody {
    std::string id, shape="box", motion="dynamic";
    Vec3 position{0}, half_extents{.5}, velocity{0}, angular_velocity{0};
    glm::dquat rotation{1,0,0,0};
    double radius=.5, half_height=.5, mass=1, friction=.5, restitution=0;
    double gravity_scale=1, linear_damping=.05, angular_damping=.05;
    std::uint32_t layer=0, mask=0xffffffffu;
    bool sensor=false, continuous=false;
    std::vector<PhysicsPart> parts;
    bool operator==(const PhysicsBody&) const = default;
};
struct PhysicsPose {
    Vec3 position, velocity, angular_velocity;
    glm::dquat rotation;
    bool awake;
};
struct PhysicsHit {
    bool hit=false;
    std::string entity;
    Vec3 point{0}, normal{0};
    double fraction=1;
};
struct PhysicsContact {
    std::string first, second, phase; // enter, stay, exit; entity IDs sorted
    Vec3 point{0}, normal{0}; // normal points from first to second
    bool sensor=false;
};
struct CharacterSettings {
    double max_slope=45, step_height=.3, floor_snap=.4, max_strength=100;
};
struct CharacterState {
    Vec3 position{0}, velocity{0}, ground_point{0}, ground_normal{0}, ground_velocity{0};
    std::string ground_entity, ground_state="in_air";
    bool grounded=false;
};

// Owns an independent Jolt world. All calls occur on the host simulation thread.
// Gameplay scene synchronization and graph event dispatch live above this layer.
class PhysicsWorld {
public:
    static constexpr std::size_t MaxBodies=4096;
    explicit PhysicsWorld(Vec3 gravity=Vec3(0,-9.81,0));
    ~PhysicsWorld();
    PhysicsWorld(const PhysicsWorld&)=delete;
    PhysicsWorld& operator=(const PhysicsWorld&)=delete;
    void add(const PhysicsBody&);
    void remove(const std::string&);
    bool contains(const std::string&) const;
    std::size_t size() const;
    PhysicsBody settings(const std::string&) const;
    static void validate(const PhysicsBody&);
    void shape(const std::string&,Vec3 half_extents,double radius,double half_height);
    void set_shape(const std::string&,const PhysicsBody&);
    PhysicsPose pose(const std::string&) const;
    void transform(const std::string&,Vec3,glm::dquat,bool wake=true);
    void velocity(const std::string&,Vec3 linear,Vec3 angular);
    void force(const std::string&,Vec3 force,Vec3 torque=Vec3(0));
    void impulse(const std::string&,Vec3);
    void motion(const std::string&,const std::string&);
    void awake(const std::string&,bool);
    void enabled(const std::string&,bool);
    void filter(const std::string&,std::uint32_t layer,std::uint32_t mask);
    void mass(const std::string&,double);
    void material(const std::string&,double friction,double restitution);
    void gravity_scale(const std::string&,double);
    void damping(const std::string&,double linear,double angular);
    void ignore_pair(const std::string&,const std::string&,bool ignore);
    void kinematic_target(const std::string&,Vec3,glm::dquat,double seconds);
    // Attach Jolt's virtual controller to an upright kinematic capsule body.
    void attach_character(const std::string&,const CharacterSettings& = {});
    static void validate_character(const PhysicsBody&,const CharacterSettings&);
    void clone_character(const std::string& source,const std::string& target);
    void detach_character(const std::string&);
    bool has_character(const std::string&) const;
    CharacterSettings character_settings(const std::string&) const;
    void configure_character(const std::string&,const CharacterSettings&);
    CharacterState character_state(const std::string&) const;
    // Desired world X/Z velocity persists until changed; jump is consumed once.
    void character_move(const std::string&,Vec3);
    bool character_jump(const std::string&,double speed);
    // Preserve feet while resizing; return false if the new capsule is obstructed.
    bool character_resize(const std::string&,double radius,double half_height);
    bool reshape_character(const std::string&,const PhysicsBody& geometry);
    void gravity(Vec3);
    // One fixed simulation step; the host owns accumulation and frame ordering.
    void step(double seconds);
    // Events belong to the most recent step; no gameplay runs inside Jolt callbacks.
    const std::vector<PhysicsContact>& contacts() const;
    Json checkpoint() const;
    // Stages and checks a complete independent world before replacing this one.
    void restore(const Json&);
    PhysicsHit raycast(Vec3 origin,Vec3 displacement,std::uint32_t mask=0xffffffffu,
                       bool include_sensors=false,const std::string& exclude="") const;
    // Uses the query's primitive shape, pose and dimensions; creates no body.
    PhysicsHit cast_shape(const PhysicsBody& query,Vec3 displacement,std::uint32_t mask=0xffffffffu,
                          bool include_sensors=false,const std::string& exclude="") const;
    std::vector<std::string> overlap_shape(const PhysicsBody& query,std::uint32_t mask=0xffffffffu,
                                         bool include_sensors=false,const std::string& exclude="") const;
    std::vector<std::string> overlap_sphere(Vec3 center,double radius,std::uint32_t mask=0xffffffffu,
                                         bool include_sensors=false,const std::string& exclude="") const;
private:
    void add_with_id(const PhysicsBody&,std::uint32_t,bool activate=true);
    struct Impl;
    std::unique_ptr<Impl> impl;
};
}
