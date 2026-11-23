//
//  widget_demo.cpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
#include <snicholls/fixture/widget.hpp>

#include <cstdio>

int main()
{
    std::printf("widget(4) = %d\n", snicholls::widget(4));
    return snicholls::widget(4) == 9 ? 0 : 1;
}
