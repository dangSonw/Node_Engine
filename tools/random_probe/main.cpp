#include "runtime.hpp"
#include <iostream>

int main() {
    int checks=0;
    auto require=[&](bool okay,const char* name) { if(!okay) throw std::runtime_error(name); ++checks; };
    try {
        rt::Ctx c; rt::SetRandomSeed(c,0);
        const auto selected=rt::RandomItem<int64_t>(c,{10,20,30,40});
        require(std::get<0>(selected)==40 && std::get<1>(selected)==3,"fixed selection reference");
        const auto weighted=rt::RandomWeightedItem<int64_t>(c,{10,20,30,40},{0,3,0,0});
        require(std::get<0>(weighted)==20 && std::get<1>(weighted)==1,"single positive weight");
        require(rt::ShuffleArray<int64_t>(c,{0,1,2,3})==rt::Array<int64_t>{2,3,1,0},"fixed Fisher-Yates reference");
        auto reject=[&](auto operation) {
            const auto before=rt::RandomCheckpoint(c); bool failed=false;
            try { operation(); } catch(const std::exception&) { failed=true; }
            require(failed && before==rt::RandomCheckpoint(c),"invalid input preserves stream");
        };
        reject([&] { rt::RandomItem<double>(c,{}); });
        reject([&] { rt::RandomWeightedItem<double>(c,{1,2},{0,0}); });
        reject([&] { rt::RandomWeightedItem<double>(c,{1,2},{-1,2}); });
        reject([&] { rt::RandomWeightedItem<double>(c,{1,2},{1}); });
        reject([&] { rt::RandomWeightedItem<double>(c,{1,2},{INFINITY,1}); });
        reject([&] { rt::RandomWeightedItem<double>(c,{1,2},{NAN,1}); });
        reject([&] { rt::RandomItem<double>(c,{NAN}); });
        reject([&] { rt::RandomShuffleOrder(c,rt::MaxCollection+1); });
        auto before=rt::RandomCheckpoint(c);
        require(rt::ShuffleArray<bool>(c,{}).empty(),"empty shuffle");
        require(rt::ShuffleArray<std::string>(c,{"only"})==rt::Array<std::string>{"only"},"singleton shuffle");
        require(std::get<1>(rt::RandomWeightedItem<int64_t>(c,{1,2,3},{0,1e-320,0}))==1,"subnormal positive weight");
        require(rt::RandomCheckpoint(c)==before,"constant operations consume no draw");
        rt::SetRandomSeed(c,42); int uniform[4]{},counts[4]{};
        for(int i=0;i<40000;++i) {
            ++uniform[std::get<1>(rt::RandomItem<int64_t>(c,{1,2,3,4}))];
            ++counts[std::get<1>(rt::RandomWeightedItem<int64_t>(c,{1,2,3,4},{0,1e308,5e307,5e307}))];
        }
        for(auto count:uniform) require(count>9300 && count<10700,"uniform selection histogram");
        require(counts[0]==0 && counts[1]>19000 && counts[1]<21000 && counts[2]>9300 && counts[2]<10700 && counts[3]>9300 && counts[3]<10700,"weighted histogram with overflowing raw sum");
        rt::Ctx next; rt::RestoreRandom(next,rt::RandomCheckpoint(c));
        require(rt::ShuffleArray<int64_t>(c,{1,2,3,4,5})==rt::ShuffleArray<int64_t>(next,{1,2,3,4,5}),"restored stream shuffle continuation");
        require(rt::RandomCheckpoint(c)==rt::RandomCheckpoint(next),"contexts remain independent and equal");
        for(int axis=0;axis<3;++axis) {
            rt::Vec3 high{1}; high[axis]=-1;
            reject([&] { rt::RandomVector(c,{0,0,0},high); });
            high[axis]=INFINITY;
            reject([&] { rt::RandomVector(c,{0,0,0},high); });
            high[axis]=NAN;
            reject([&] { rt::RandomVector(c,{0,0,0},high); });
        }
        before=rt::RandomCheckpoint(c);
        require(rt::RandomVector(c,{1,2,3},{1,2,3})==rt::Vec3(1,2,3),"constant vector");
        require(rt::RandomCheckpoint(c)==before,"constant vector consumes no draw");
        rt::SetRandomSeed(c,42); rt::Vec3 mean{0},squares{0},box_mean{0}; int bands[10]{},octants[8]{};
        double max_length_error=0; bool box_bounds=true,finite_directions=true;
        for(int i=0;i<40000;++i) {
            const auto direction=rt::RandomDirection(c),point=rt::RandomVector(c,{-2,4,-5},{8,4,3});
            mean+=direction; squares+=direction*direction; box_mean+=point;
            max_length_error=std::max(max_length_error,std::abs(glm::dot(direction,direction)-1));
            for(int axis=0;axis<3;++axis) finite_directions &= std::isfinite(direction[axis]) && std::abs(direction[axis])<=1;
            box_bounds &= point.x>=-2 && point.x<8 && point.y==4 && point.z>=-5 && point.z<3;
            ++bands[std::min(9,int((direction.y+1)*5))];
            ++octants[(direction.x>=0 ? 1:0)+(direction.y>=0 ? 2:0)+(direction.z>=0 ? 4:0)];
        }
        mean/=40000; squares/=40000; box_mean/=40000;
        require(finite_directions && max_length_error<1e-14,"finite unit directions");
        require(box_bounds && std::abs(box_mean.x-3)<.07 && std::abs(box_mean.z+1)<.07,"uniform box bounds and means");
        for(int axis=0;axis<3;++axis) require(std::abs(mean[axis])<.015 && std::abs(squares[axis]-1./3)<.008,"sphere first and second moments");
        for(auto count:bands) require(count>3600 && count<4400,"equal-area height bands");
        for(auto count:octants) require(count>4500 && count<5500,"sphere octants");
        rt::RestoreRandom(next,rt::RandomCheckpoint(c));
        require(rt::RandomVector(c,{-1,-1,-1},{1,1,1})==rt::RandomVector(next,{-1,-1,-1},{1,1,1}),"restored vector continuation");
        require(rt::RandomDirection(c)==rt::RandomDirection(next),"restored direction continuation");
        std::cout<<rt::Json({{"passed",true},{"checks",checks},{"samples",40000},{"uniform",uniform},{"weighted",counts},
            {"sphere_mean",{mean.x,mean.y,mean.z}},{"sphere_second_moment",{squares.x,squares.y,squares.z}},
            {"sphere_bands",bands},{"sphere_octants",octants},{"max_squared_length_error",max_length_error}}).dump()<<"\n";
    } catch(const std::exception& e) { std::cerr<<e.what()<<"\n"; return 1; }
}
