# A shared runtime compatibility token, identical for Preview and generated games.
file(GLOB_RECURSE checkpoint_sources CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/runtime/*.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/runtime/*.hpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/runtime/*.spv")
file(GLOB checkpoint_dependencies "${CMAKE_CURRENT_SOURCE_DIR}/cmake/*.cmake" "${CMAKE_CURRENT_SOURCE_DIR}/deps/*/upstream.txt")
list(APPEND checkpoint_sources ${checkpoint_dependencies}
  "${CMAKE_CURRENT_SOURCE_DIR}/CMakeLists.txt" "${CMAKE_CURRENT_SOURCE_DIR}/nodes/registry.yaml")
list(SORT checkpoint_sources)
set(checkpoint_manifest "")
foreach(path IN LISTS checkpoint_sources)
  file(SHA256 "${path}" digest)
  file(RELATIVE_PATH relative "${CMAKE_CURRENT_SOURCE_DIR}" "${path}")
  string(APPEND checkpoint_manifest "${relative}:${digest}\n")
endforeach()
string(SHA256 checkpoint_runtime_id "${checkpoint_manifest}")
# Only this translation unit consumes the identity; other runtime objects remain cacheable.
set_property(SOURCE runtime/src/checkpoint_identity.cpp APPEND PROPERTY
  COMPILE_DEFINITIONS NODE_ENGINE_CHECKPOINT_ABI="${checkpoint_runtime_id}")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${checkpoint_sources})
