//
//  greeter.hpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
/// \file
/// \brief The greeter capability: its concept.

#ifndef snicholls_fixture_concepts_greeter_hpp
#define snicholls_fixture_concepts_greeter_hpp

#include <concepts>

namespace snicholls
{
/// \brief A type that greets: greet() returns a number.
template <class T>
concept greeter = requires(const T& t) {
    { t.greet() } -> std::same_as<int>;
};
}

#endif
