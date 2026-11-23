//
//  twice.hpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
/// \file
/// \brief An internal.

#ifndef snicholls_fixture_detail_twice_hpp
#define snicholls_fixture_detail_twice_hpp

namespace snicholls::detail
{
/// \brief Twice x.
/// \param x the value.
/// \return 2x.
constexpr int twice(int x) noexcept { return 2 * x; }
}

#endif
