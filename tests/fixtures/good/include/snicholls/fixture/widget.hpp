//
//  widget.hpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
/// \file
/// \brief A function to test.

#ifndef snicholls_fixture_widget_hpp
#define snicholls_fixture_widget_hpp

#include <snicholls/fixture/detail/twice.hpp>

namespace snicholls
{
/// \brief Twice x plus one.
/// \param x the value.
/// \return 2x + 1.
constexpr int widget(int x) noexcept { return detail::twice(x) + 1; }
}

#endif
