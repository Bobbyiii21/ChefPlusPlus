#include "algorithms/sort.h"
#include "core/types.h"
#include <cassert>

int main() {
    mathcore::core::Vector v(5);
    v[0] = 5.0; v[1] = 3.0; v[2] = 1.0; v[3] = 4.0; v[4] = 2.0;

    mathcore::algorithms::sort_vector(v);

    assert(v[0] == 1.0);
    assert(v[1] == 2.0);
    assert(v[2] == 3.0);
    assert(v[3] == 4.0);
    assert(v[4] == 5.0);

    int idx = mathcore::algorithms::binary_search(v, 3.0);
    assert(idx == 2);

    int not_found = mathcore::algorithms::binary_search(v, 99.0);
    assert(not_found == -1);

    return 0;
}
