#pragma once
#include <cstddef>
#include <new>

namespace mathcore {
namespace core {

class AlignedBuffer {
public:
    AlignedBuffer(size_t size, size_t alignment = alignof(std::max_align_t));
    ~AlignedBuffer();

    AlignedBuffer(const AlignedBuffer&) = delete;
    AlignedBuffer& operator=(const AlignedBuffer&) = delete;

    void* data();
    const void* data() const;
    size_t size() const;

private:
    void* data_;
    size_t size_;
    size_t alignment_;
};

} // namespace core
} // namespace mathcore
