//
//  greeter_test.cpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
#include <snicholls/fixture/concepts/greeter.hpp>

struct hello { int greet() const { return 1; } };
struct mute {};
static_assert(snicholls::greeter<hello>);
static_assert(!snicholls::greeter<mute>);

int main() { return 0; }
