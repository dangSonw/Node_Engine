#include "runtime.hpp"
#include <iostream>
int main() {
    try {
        int checks=0; auto require=[&](bool okay,const char* label){ if(!okay) throw std::runtime_error(label); ++checks; };
        const rt::Json old_program={{"events",{{"start",rt::Json::array()},{"update",rt::Json::array()}}}};
        rt::ValidateFrameEvents(old_program); ++checks;
        for(const auto* phase:{"start","update","fixed_update","late_update","quit","world_pause"}) {
            auto bad=old_program; bad["events"][phase]=rt::Json::object(); bool failed=false;
            try { rt::ValidateFrameEvents(bad); } catch(const std::exception& e) { failed=std::string(e.what()).find(phase)!=std::string::npos; }
            require(failed,"malformed frame phase accepted or unidentified");
        }
        auto missing=old_program; missing["events"].erase("update"); bool rejected=false;
        try { rt::ValidateFrameEvents(missing); } catch(const std::exception&) { rejected=true; }
        require(rejected,"missing required frame phase accepted");
        rt::Ctx c;
        auto clock=[&]{return rt::Json{{"dt",c.dt},{"unscaled",c.unscaled_dt},{"real_dt",c.real_dt},{"scale",c.time_scale},
            {"time",c.time},{"real",c.real_time},{"frame",c.frame},{"frozen",c.time_frozen}};};
        auto reject=[&](auto operation) {
            auto before=clock(); bool failed=false;
            try{operation();}catch(const std::exception&){failed=true;}
            require(failed&&before==clock(),"invalid clock operation mutated state");
        };
        for(auto scale:{-1.,double(INFINITY),double(NAN)}) reject([&]{rt::SetTimeScale(c,scale);});
        for(auto elapsed:{-1.,double(INFINITY),double(NAN),61.}) reject([&]{rt::BeginGameFrame(c,elapsed);});
        reject([&]{rt::BeginGameFrame(c,.1,.2);});
        rt::SetTimeScale(c,2); reject([&]{rt::BeginGameFrame(c,1);});
        rt::SetTimeScale(c,1e308); reject([&]{rt::BeginGameFrame(c,60);});
        rt::SetTimeScale(c,.25); rt::BeginGameFrame(c,2,.1);
        require(c.dt==.025&&c.unscaled_dt==.1&&c.real_dt==2,"stall splits real and capped simulation delta");
        rt::SetTimeScale(c,0); require(c.dt==.025&&!c.time_frozen,"scale remains stable inside current frame");
        rt::EndGameFrame(c); require(c.time==.025&&c.real_time==2&&c.frame==1,"independent elapsed clocks");
        rt::BeginGameFrame(c,1,.1); require(c.dt==0&&c.time_frozen,"next frame freezes");
        rt::EndGameFrame(c); require(c.time==.025&&c.real_time==3,"real time advances when game is frozen");
        rt::SetTimeScale(c,1); rt::BeginGameFrame(c,.1); rt::EndGameFrame(c);
        require(c.time==.125&&c.real_time==3.1&&c.frame==3,"resume preserves elapsed clocks");
        c.real_time=1.7976931348623157e308;
        reject([&]{rt::BeginGameFrame(c,1.7976931348623157e308,.1);});
        c.real_time=0; c.frame=UINT64_MAX; reject([&]{rt::BeginGameFrame(c,.1);});
        const rt::Json scene={{"version",1},{"entities",rt::Json::array()},{"variables",rt::Json::object()}};
        const rt::Json identity={{"probe","application quit"}};
        rt::Ctx app; rt::LoadScene(app,scene); rt::PrepareAudio(app,std::filesystem::current_path()); rt::PrepareUi(app,std::filesystem::current_path()); int calls=0;
        const auto saved=rt::GameCheckpoint(app,identity);
        rt::QuitApplication(app); rt::QuitApplication(app);
        require(app.quit_requested && !app.quit_dispatched,"quit request must defer dispatch");
        auto staged=rt::StageGameCheckpoint(app,identity,saved,std::filesystem::current_path());
        rt::CommitGameCheckpoint(app,std::move(staged));
        require(app.quit_requested && !app.quit_dispatched,"Load must preserve pending host quit intent");
        auto callback=[&]{++calls; rt::QuitApplication(app);};
        rt::FinishApplication(app,callback,[]{},[]{});
        require(app.quit_requested && app.quit_dispatched && calls==1,"shutdown must dispatch exactly once");
        rt::FinishApplication(app,callback,[]{},[]{});
        require(calls==1,"repeated shutdown must not retry callback");
        require(rt::GameCheckpoint(app,identity)==saved,"host shutdown intent leaked into checkpoint");
        staged=rt::StageGameCheckpoint(app,identity,saved,std::filesystem::current_path());
        rt::CommitGameCheckpoint(app,std::move(staged));
        require(app.quit_dispatched,"restoration must not rearm a dispatched shutdown");
        rt::LoadScene(app,scene);
        require(!app.quit_requested && !app.quit_dispatched,"fresh scene must clear host shutdown state");
        {
            rt::ExecutionScope scope(app); bool failed=false;
            try { rt::FinishApplication(app,callback,[]{},[]{}); } catch(const std::exception&) { failed=true; }
            require(failed && !app.quit_requested && calls==1,"shutdown entered an active graph");
        }
        bool failed=false;
        try { rt::FinishApplication(app,[&]{++calls; throw std::runtime_error("cleanup failure");},[]{},[]{}); }
        catch(const std::exception& e) { failed=std::string(e.what())=="cleanup failure"; }
        require(failed && app.quit_dispatched && calls==2,"failed shutdown did not retain its dispatch guard");
        rt::FinishApplication(app,callback,[]{},[]{}); require(calls==2,"failed callback was retried");
        rt::Ctx pause; rt::LoadScene(pause,scene); rt::PrepareAudio(pause,std::filesystem::current_path()); rt::PrepareUi(pause,std::filesystem::current_path());
        rt::BindWorldPauseEvent(pause,1017,"pause",[](rt::Ctx& c,rt::EntityRef,rt::EntityRef,const std::vector<rt::Value>&){c.logs.push_back("pause");});
        rt::BindWorldPauseEvent(pause,1018,"resume",[](rt::Ctx& c,rt::EntityRef,rt::EntityRef,const std::vector<rt::Value>&){c.logs.push_back("resume");});
        rt::SetTimeScale(pause,.25); rt::BeginGameFrame(pause,.125);
        rt::PauseWorld(pause); rt::PauseWorld(pause);
        require(pause.world_paused && pause.dt==.03125 && !pause.time_frozen && pause.logs.empty(),"pause changed current-frame delta or dispatched recursively");
        const auto paused=rt::GameCheckpoint(pause,identity);
        require(paused.at("clock").at("paused")==true && paused.at("events").at("queue").size()==1,"pending pause event missing or duplicated in checkpoint");
        auto restored_pause=rt::StageGameCheckpoint(pause,identity,paused,std::filesystem::current_path());
        rt::CommitGameCheckpoint(pause,std::move(restored_pause));
        require(pause.world_paused && rt::GameCheckpoint(pause,identity)==paused,"pause checkpoint did not restore exactly");
        rt::DrainEvents(pause); require(pause.logs==std::vector<std::string>{"pause"},"restored pause event did not deliver once");
        rt::BeginGameFrame(pause,.125); rt::EndGameFrame(pause);
        require(pause.dt==0 && pause.time_frozen && pause.time==0 && pause.real_time==.125,"pause did not freeze only game time");
        const auto settled=rt::GameCheckpoint(pause,identity);
        restored_pause=rt::StageGameCheckpoint(pause,identity,settled,std::filesystem::current_path());
        rt::CommitGameCheckpoint(pause,std::move(restored_pause)); rt::DrainEvents(pause);
        require(pause.logs==std::vector<std::string>{"pause"},"Load synthesized a pause callback");
        rt::BeginGameFrame(pause,.125);
        rt::SetTimeScale(pause,2); rt::ResumeWorld(pause); rt::ResumeWorld(pause);
        require(!pause.world_paused && pause.dt==0 && pause.time_frozen && pause.time_scale==2,"resume changed current-frame delta or overwrote scale");
        rt::DrainEvents(pause); require(pause.logs==std::vector<std::string>{"pause","resume"},"resume callback was lost or duplicated");
        rt::BeginGameFrame(pause,.125); rt::EndGameFrame(pause);
        require(pause.time==.25 && pause.real_time==.25 && pause.dt==.25,"resumed world did not use requested scale");
        const auto before_pause=rt::GameCheckpoint(pause,identity); const auto world=pause.world;
        for(const auto invalid:{rt::Json(1),rt::Json("true"),rt::Json(nullptr),rt::Json::array()}) {
            auto corrupt=before_pause; corrupt["clock"]["paused"]=invalid; bool failed=false;
            try { auto candidate=rt::StageGameCheckpoint(pause,identity,corrupt,std::filesystem::current_path()); } catch(const std::exception&) { failed=true; }
            require(failed && pause.world==world && rt::GameCheckpoint(pause,identity)==before_pause,"invalid pause flag mutated live state");
        }
        auto legacy=before_pause; legacy["clock"].erase("paused");
        restored_pause=rt::StageGameCheckpoint(pause,identity,legacy,std::filesystem::current_path());
        require(!restored_pause.world_paused,"legacy checkpoint did not default to unpaused");
        rt::PauseWorld(pause); rt::LoadScene(pause,scene);
        require(!pause.world_paused,"new scene retained pause state");
        bool invalid_event=false; try {rt::BindWorldPauseEvent(pause,999,"bad",{});} catch(const std::exception&) {invalid_event=true;}
        require(invalid_event,"invalid pause event ID accepted");
        auto pause_program=old_program;
        pause_program["events"]["world_pause"]=rt::Json::array({{{"node","pause"},{"event",1017},{"body",rt::Json::array()}}});
        rt::ValidateFrameEvents(pause_program); ++checks;
        for(int corruption=0;corruption<7;++corruption) {
            auto bad=pause_program; auto& h=bad["events"]["world_pause"][0];
            if(corruption==0) h["event"]=1017.5;
            else if(corruption==1) h["event"]=999;
            else if(corruption==2) h["body"]=rt::Json::object();
            else if(corruption==3) h["node"]="";
            else if(corruption==4) h["node"]=1;
            else if(corruption==5) h["extra"]=0;
            else h.erase("body");
            bool failed=false; try {rt::ValidateFrameEvents(bad);} catch(const std::exception&) {failed=true;}
            require(failed,"invalid pause handler metadata accepted");
        }
        std::cout<<rt::Json{{"passed",true},{"checks",checks}}.dump()<<"\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
