#pragma once
#include <Jolt/Physics/StateRecorder.h>
#include <bit>
#include <cstring>
#include <set>
#include <tuple>

namespace rt::physics_checkpoint {
inline void Require(bool ok,const char* why) {
    if(!ok) throw std::runtime_error(std::string("Invalid physics checkpoint: ")+why);
}
inline constexpr std::size_t MaxBytes=16*1024*1024;
struct Recorder final : JPH::StateRecorder {
    std::vector<std::uint8_t> bytes;
    std::size_t cursor=0;
    bool failed=false;
    void WriteBytes(const void* data,std::size_t size) override {
        Require(size<=MaxBytes-bytes.size(),"native state exceeds 16 MiB");
        const auto* start=static_cast<const std::uint8_t*>(data); bytes.insert(bytes.end(),start,start+size);
    }
    void ReadBytes(void* data,std::size_t size) override {
        if(size>bytes.size()-cursor) { failed=true; std::memset(data,0,size); return; }
        std::memcpy(data,bytes.data()+cursor,size); cursor+=size;
    }
    bool IsEOF() const override { return cursor==bytes.size(); }
    bool IsFailed() const override { return failed; }
    std::string hex() const {
        constexpr char digits[]="0123456789abcdef"; std::string result; result.reserve(bytes.size()*2);
        for(auto byte:bytes) { result.push_back(digits[byte>>4]); result.push_back(digits[byte&15]); } return result;
    }
    void decode(const Json& value) {
        Require(value.is_string(),"native state must be hex text");
        const auto& s=value.get_ref<const std::string&>(); Require(s.size()<=2*MaxBytes&&s.size()%2==0,"native state length");
        const auto digit=[](char c)->unsigned { if(c>='0'&&c<='9') return c-'0'; if(c>='a'&&c<='f') return c-'a'+10; Require(false,"native state hex digit"); return 0; };
        bytes.reserve(s.size()/2);
        for(std::size_t i=0;i<s.size();i+=2) bytes.push_back(std::uint8_t((digit(s[i])<<4)|digit(s[i+1])));
    }
};
inline std::uint32_t UInt(const Json& value,std::uint32_t max=UINT32_MAX) {
    Require(value.is_number_integer()&&(value.is_number_unsigned()||value.get<std::int64_t>()>=0),"unsigned integer required");
    const auto result=value.get<std::uint64_t>(); Require(result<=max,"integer range"); return std::uint32_t(result);
}
inline void NativeID(std::uint32_t id) { Require(!(id&0x80000000u)&&(id&0x7fffffu)<PhysicsWorld::MaxBodies,"body ID range"); }
// The parser is tied to the pinned Jolt 5.6.0 rigid-body SaveState layout.
// Preflight the entire buffer before Jolt sees it (its reader assumes trusted data).
struct Cursor {
    const std::vector<std::uint8_t>& bytes;
    std::size_t offset=0;
    template<class T> T read() {
        Require(sizeof(T)<=bytes.size()-offset,"truncated native state");
        T value; std::memcpy(&value,bytes.data()+offset,sizeof(T)); offset+=sizeof(T); return value;
    }
    bool boolean() { auto b=read<std::uint8_t>(); Require(b<=1,"boolean encoding"); return b!=0; }
    template<class T> double number(double low,double high) {
        auto x=read<T>(); Require(std::isfinite(x)&&x>=low&&x<=high,"non-finite or out-of-range native number"); return x;
    }
    template<class T> double vector(int count,double bound) {
        double norm=0; for(int i=0;i<count;++i) { auto x=number<T>(-bound,bound); norm+=x*x; } return norm;
    }
    void body() {
        vector<double>(3,1e12);
        Require(std::abs(vector<float>(4,1.001)-1)<.002,"body quaternion");
        vector<float>(6,1e4); vector<float>(6,1e18);
        vector<double>(3,1e12);
        for(int i=0;i<3;++i) { vector<float>(3,1e12); number<float>(0,1e12); }
        number<float>(0,1e9); Require(boolean(),"sleep policy");
    }
    void end() { Require(offset==bytes.size(),"trailing native bytes"); }
};
struct BodyInfo { bool enabled,active,moving; const Recorder* state; };
inline void ValidateBody(const Recorder& state) { Cursor cursor{state.bytes}; cursor.body(); cursor.end(); }
inline void ValidateCharacter(const Recorder& state,std::uint32_t self) {
    static_assert(sizeof(JPH::CharacterBase::EGroundState)==4&&sizeof(JPH::EMotionType)==1);
    Cursor c{state.bytes}; Require(c.read<std::uint32_t>()<=3,"character ground state");
    auto body=[&](bool optional) {
        const auto id=c.read<std::uint32_t>();
        if(optional&&id==UINT32_MAX) return;
        NativeID(id); Require(id!=self,"character contact with self");
    };
    auto normal=[&](bool optional) {
        const auto n=c.vector<float>(3,1.001);
        Require((optional&&n==0)||std::abs(n-1)<.002,"character contact normal");
    };
    body(true); Require(c.read<std::uint32_t>()==UINT32_MAX,"character primitive ground subshape");
    c.vector<double>(3,1e12); normal(true); c.vector<float>(3,1e4);
    c.vector<double>(3,1e12); Require(std::abs(c.vector<float>(4,1.001)-1)<.002,"character rotation");
    c.vector<float>(3,1e4); c.number<float>(0,.100001); c.boolean();
    const auto count=c.read<std::uint32_t>(); Require(count<=1024,"character contact count");
    for(std::uint32_t i=0;i<count;++i) {
        body(false); Require(c.read<std::uint32_t>()==UINT32_MAX,"unsupported virtual character reference");
        Require(c.read<std::uint32_t>()==UINT32_MAX,"character primitive contact subshape");
        c.vector<double>(3,1e12); c.vector<float>(3,1e4); normal(false); normal(false);
        c.number<float>(-1e12,1e12); c.number<float>(0,1.0001);
        Require(c.read<std::uint8_t>()<=2,"character contact motion");
        Require(!c.boolean()&&c.boolean(),"character solid collision contact"); c.boolean(); c.boolean();
    }
    c.end();
}
inline void ValidateWorld(const Recorder& state,const std::map<std::uint32_t,BodyInfo>& bodies) {
    static_assert(std::endian::native==std::endian::little&&sizeof(float)==4&&sizeof(double)==8&&sizeof(bool)==1);
    Cursor c{state.bytes}; Require(c.read<std::uint8_t>()==15,"native state flags");
    c.number<float>(0,.100001); c.vector<float>(3,1e5);
    const auto count=c.read<std::uint32_t>(); std::size_t enabled=0;
    for(const auto& [_,body]:bodies) enabled+=body.enabled;
    Require(count==enabled,"enabled body count"); std::set<std::uint32_t> seen;
    for(std::size_t i=0;i<count;++i) {
        auto id=c.read<std::uint32_t>(); auto it=bodies.find(id);
        Require(it!=bodies.end()&&it->second.enabled&&seen.insert(id).second,"native body membership");
        const auto& body=it->second; auto active=c.boolean(); Require(active==body.active&&(!active||body.moving),"body activation");
        auto begin=c.offset; c.body();
        Require(c.offset-begin==body.state->bytes.size()&&std::equal(body.state->bytes.begin(),body.state->bytes.end(),state.bytes.begin()+begin),"inconsistent body state");
    }
    const auto pairs=c.read<std::uint32_t>(); Require(pairs<=16384,"contact pair count");
    using SubShapePair=std::tuple<std::uint32_t,std::uint32_t,std::uint32_t,std::uint32_t>;
    std::set<std::pair<std::uint32_t,std::uint32_t>> pair_ids;
    std::set<SubShapePair> manifolds;
    auto subshape=[&]() {
        auto a=c.read<std::uint32_t>(),sa=c.read<std::uint32_t>(),b=c.read<std::uint32_t>(),sb=c.read<std::uint32_t>();
        NativeID(a); NativeID(b); Require(a<b,"unordered contact subshape pair");
        // UINT32_MAX is Jolt's primitive sentinel; compound and mesh shapes
        // store the encoded leaf SubShapeID here. Keep the ID opaque because
        // the shape tree is reconstructed by the preceding body settings.
        Require(manifolds.emplace(a,sa,b,sb).second&&manifolds.size()<=65536,"duplicate or excessive contact manifold");
        return SubShapePair{a,sa,b,sb};
    };
    for(std::size_t i=0;i<pairs;++i) {
        auto a=c.read<std::uint32_t>(),b=c.read<std::uint32_t>(); NativeID(a); NativeID(b);
        Require(a<b&&pair_ids.emplace(a,b).second,"duplicate or unordered contact pair");
        c.vector<float>(3,1e12); Require(c.vector<float>(3,1.001)<=1.002,"contact rotation");
        auto count=c.read<std::uint32_t>(); Require(count<=64,"contact manifold count");
        for(std::size_t j=0;j<count;++j) {
            const auto sub=subshape(); Require(std::get<0>(sub)==a&&std::get<2>(sub)==b,"manifold belongs to another pair");
            auto points=c.read<std::uint16_t>(); Require(points<=4,"contact point count");
            auto norm=c.vector<float>(3,1.001); Require((points==0&&norm==0)||std::abs(norm-1)<.002,"contact normal");
            c.vector<float>(3,1e18);
            for(int k=0;k<points;++k) { c.vector<float>(6,1e12); c.number<float>(0,1e18); }
        }
    }
    auto ccd=c.read<std::uint32_t>(); Require(ccd<=16384,"CCD manifold count");
    for(std::size_t i=0;i<ccd;++i) subshape();
    Require(c.read<std::uint32_t>()==0,"constraints are unsupported"); c.end();
}
}
