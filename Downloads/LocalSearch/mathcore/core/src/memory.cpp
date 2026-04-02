#include "core/memory.h"
#include <stdexcept>

namespace mathcore {
namespace core {

AlignedBuffer::AlignedBuffer(size_t size, size_t alignment)
    : size_(size), alignment_(alignment)
{
    if (size == 0) {
        throw std::invalid_argument("Buffer size must be positive");
    }
    data_ = ::operator new(size, std::align_val_t{alignment});
}

AlignedBuffer::~AlignedBuffer() {
    ::operator delete(data_, std::align_val_t{alignment_});
}

void* AlignedBuffer::data() { return data_; }
const void* AlignedBuffer::data() const { return data_; }
size_t AlignedBuffer::size() const { return size_; }

} // namespace core
} // namespace mathcore
