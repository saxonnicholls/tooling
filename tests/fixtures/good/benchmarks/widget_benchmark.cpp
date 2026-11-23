//
//  widget_benchmark.cpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
#include <snicholls/fixture/widget.hpp>

int main(int argc, char**)
{
    int sum = 0;
    for (int i = 0; i < 1000; ++i)
        sum += snicholls::widget(i + argc);
    return sum > 0 ? 0 : 1;
}
