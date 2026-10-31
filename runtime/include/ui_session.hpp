#pragma once
#include <filesystem>
#include <memory>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>

struct SDL_Window;
union SDL_Event;
namespace Rml { class RenderInterface; }
namespace rt {
struct UiEvent {
    std::string document, element, type, value;
    bool checked=false;
    uint64_t generation=0;
};
// A scene owns one session. Sessions may coexist while a replacement scene is
// prepared, and share the process-wide RmlUi/font lifetime without sharing widgets.
class UiSession {
public:
    UiSession(const std::filesystem::path& font, Rml::RenderInterface* renderer=nullptr, SDL_Window* window=nullptr,
              const std::filesystem::path& assets={},bool platform_active=true);
    ~UiSession();
    void suspend_platform() noexcept;
    void activate_platform() noexcept;
    UiSession(const UiSession&)=delete;
    UiSession& operator=(const UiSession&)=delete;
    void load(const std::string& document, const std::string& rml, const std::string& source_url="");
    void destroy(const std::string& document);
    bool contains(const std::string& document) const;
    void show(const std::string& document, bool visible);
    void set_text(const std::string& document,const std::string& element,const std::string& text);
    std::string text(const std::string& document,const std::string& element) const;
    void set_value(const std::string& document,const std::string& element,double value);
    double value(const std::string& document,const std::string& element) const;
    void set_checked(const std::string& document,const std::string& element,bool checked);
    bool checked(const std::string& document,const std::string& element) const;
    void set_enabled(const std::string& document,const std::string& element,bool enabled);
    bool enabled(const std::string& document,const std::string& element) const;
    void set_style(const std::string& document,const std::string& element,const std::string& property,const std::string& value);
    void focus(const std::string& document,const std::string& element);
    void update(double seconds,int pixel_width,int pixel_height,float density=1);
    void render(); // Inside the renderer's begin/end frame pair.
    bool process(SDL_Event&);
    bool pointer_move(int x,int y,int modifiers=0);
    bool pointer_button(int button,bool down,int modifiers=0);
    bool text_input(const std::string& text);
    bool key_input(int rml_key,bool down,int modifiers=0);
    std::vector<UiEvent> take_events();
    bool alive(const UiEvent&) const;
    void clear_input();
    nlohmann::json snapshot() const;
    nlohmann::json checkpoint() const;
    // Apply only to a candidate session with matching, newly loaded templates.
    // The owning runtime swaps the candidate after all validation succeeds.
    void restore_checkpoint(const nlohmann::json&);
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
