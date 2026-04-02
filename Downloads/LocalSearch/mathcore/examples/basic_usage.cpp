#include "analytics/stats.h"
#include "algorithms/sort.h"
#include "core/types.h"
#include <iostream>

int main() {
    mathcore::core::Vector data(5);
    data[0] = 3.0;
    data[1] = 1.0;
    data[2] = 4.0;
    data[3] = 1.0;
    data[4] = 5.0;

    std::cout << "Mean: " << mathcore::analytics::mean(data) << "\n";
    std::cout << "Std Dev: " << mathcore::analytics::std_deviation(data) << "\n";

    mathcore::algorithms::sort_vector(data);
    std::cout << "Sorted: ";
    for (size_t i = 0; i < data.size(); ++i) {
        std::cout << data[i] << " ";
    }
    std::cout << "\n";

    return 0;
}
