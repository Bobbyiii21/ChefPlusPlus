#include "algorithms/reduce.h"
#include <stdexcept>

namespace mathcore {
namespace algorithms {

double reduce_sum(const core::Vector& vec) {
    double sum = 0.0;
    for (size_t i = 0; i < vec.size(); ++i) {
        sum += vec[i];
    }
    return sum;
}

double reduce_product(const core::Vector& vec) {
    if (vec.size() == 0) {
        throw std::invalid_argument("Cannot reduce empty vector");
    }
    double product = 1.0;
    for (size_t i = 0; i < vec.size(); ++i) {
        product *= vec[i];
    }
    return product;
}

double reduce_max(const core::Vector& vec) {
    if (vec.size() == 0) {
        throw std::invalid_argument("Cannot reduce empty vector");
    }
    double max_val = vec[0];
    for (size_t i = 1; i < vec.size(); ++i) {
        if (vec[i] > max_val) max_val = vec[i];
    }
    return max_val;
}

double reduce_min(const core::Vector& vec) {
    if (vec.size() == 0) {
        throw std::invalid_argument("Cannot reduce empty vector");
    }
    double min_val = vec[0];
    for (size_t i = 1; i < vec.size(); ++i) {
        if (vec[i] < min_val) min_val = vec[i];
    }
    return min_val;
}

} // namespace algorithms
} // namespace mathcore
