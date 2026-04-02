#include "analytics/stats.h"
#include "core/types.h"
#include <cassert>
#include <cmath>

int main() {
    mathcore::core::Vector v(4);
    v[0] = 2.0; v[1] = 4.0; v[2] = 4.0; v[3] = 6.0;

    double m = mathcore::analytics::mean(v);
    assert(std::abs(m - 4.0) < 1e-10);

    double var = mathcore::analytics::variance(v);
    assert(std::abs(var - 2.6667) < 1e-3);

    double std_dev = mathcore::analytics::std_deviation(v);
    assert(std::abs(std_dev - std::sqrt(var)) < 1e-10);

    return 0;
}
