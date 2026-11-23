//
//  greeter_test.cpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
#include <snicholls/fixture/interfaces/greeter.hpp>

struct hello { int greet() const { return 7; } };

int main()
{
    const snicholls::greeter_adapter<hello> a{hello{}};
    const snicholls::greeter_interface& g = a;
    return g.greet() == 7 ? 0 : 1;
}
