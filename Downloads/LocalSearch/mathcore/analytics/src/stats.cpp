#include "analytics/stats.h"
#include "algorithms/reduce.h"
#include "core/types.h"
#include <cmath>
#include <stdexcept>

namespace mathcore {
namespace analytics {

double mean(const core::Vector& vec) {
    if (vec.size() == 0) {
        throw std::invalid_argument("Cannot compute mean of empty vector");
    }
    double s = algorithms::reduce_sum(vec);
    return s / static_cast<double>(vec.size());
}

double variance(const core::Vector& vec) {
    if (vec.size() < 2) {
        throw std::invalid_argument("Variance requires at least 2 elements");
    }
    double m = mean(vec);
    double sum_sq = 0.0;
    for (size_t i = 0; i < vec.size(); ++i) {
        double diff = vec[i] - m;
        sum_sq += diff * diff;
    }
    return sum_sq / static_cast<double>(vec.size() - 1);
}

double std_deviation(const core::Vector& vec) {
    return std::sqrt(variance(vec));
}

} // namespace analytics
} // namespace mathcore
