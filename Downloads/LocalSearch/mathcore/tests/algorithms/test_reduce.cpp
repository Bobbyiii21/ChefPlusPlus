#include "algorithms/reduce.h"
#include "core/types.h"
#include <cassert>

int main() {
    mathcore::core::Vector v(4);
    v[0] = 1.0; v[1] = 2.0; v[2] = 3.0; v[3] = 4.0;

    assert(mathcore::algorithms::reduce_sum(v) == 10.0);
    assert(mathcore::algorithms::reduce_product(v) == 24.0);
    assert(mathcore::algorithms::reduce_max(v) == 4.0);
    assert(mathcore::algorithms::reduce_min(v) == 1.0);

    return 0;
}
