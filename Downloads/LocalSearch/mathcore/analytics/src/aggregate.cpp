#include "analytics/stats.h"
#include "algorithms/reduce.h"
#include "core/types.h"
#include <stdexcept>

namespace mathcore {
namespace analytics {

double sum(const core::Vector& vec) {
    return algorithms::reduce_sum(vec);
}

double min_val(const core::Vector& vec) {
    return algorithms::reduce_min(vec);
}

double max_val(const core::Vector& vec) {
    return algorithms::reduce_max(vec);
}

core::Vector column_means(const core::Matrix& mat) {
    if (mat.rows() == 0) {
        throw std::invalid_argument("Matrix has no rows");
    }
    core::Vector means(mat.cols());
    for (size_t col = 0; col < mat.cols(); ++col) {
        double col_sum = 0.0;
        for (size_t row = 0; row < mat.rows(); ++row) {
            col_sum += mat.at(row, col);
        }
        means[col] = col_sum / static_cast<double>(mat.rows());
    }
    return means;
}

} // namespace analytics
} // namespace mathcore
