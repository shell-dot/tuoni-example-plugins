#include "TLV.h"
#include"Conversions.h"
#include<string>
#include<cstddef>
#include<utility>

TLV::~TLV() noexcept
{
	clear();
}

void TLV::clear() noexcept
{
	// Detach each sibling before releasing it. Cleanup must neither allocate a
	// temporary container nor recursively destroy an entire sibling chain.
	auto currentChild = std::move(child);
	while (currentChild)
	{
		auto nextChild = std::move(currentChild->sibling);
		currentChild.reset();
		currentChild = std::move(nextChild);
	}
	sibling.reset();
	value.clear();
}

bool TLV::load(const std::vector<byte>&& dataVec)
{
	PBYTE data = (PBYTE)dataVec.data();
	UINT32 inputLength = (UINT32)dataVec.size();
	return load_internal(data, inputLength);
}

bool TLV::load(const std::vector<byte>& dataVec)
{
	PBYTE data = (PBYTE)dataVec.data();
	UINT32 inputLength = (UINT32)dataVec.size();
	return load_internal(data, inputLength);
}

bool TLV::load_internal(PBYTE data, UINT32 inputLength)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (sizeof(TLVheader) > inputLength)
	{
		return false;
	}
	PTLVheader header = (PTLVheader)data;
	if (header->length + sizeof(TLVheader) > inputLength)
	{
		return false;
	}
	if (header->type & TLV_PARENT_TYPE_FLAG)
		parent = true;
	type = header->type & (~TLV_PARENT_TYPE_FLAG);
	UINT32 length = header->length;

	if (parent)
	{
		//Parent type
		PBYTE ptr = data + sizeof(TLVheader);
		std::shared_ptr<TLV> lastChild;
		UINT32 left = length;
		while (left)
		{
			std::shared_ptr<TLV> newChild(new TLV());
			if (!newChild->load_internal(ptr, left))
			{
				clear();
				return false;
			}
			left -= newChild->getTotalLength();
			ptr += newChild->getTotalLength();
			if (!lastChild.get())
			{
				child = newChild;
				lastChild = newChild;
			}
			else
			{
				lastChild->sibling = newChild;
				lastChild = newChild;
			}

		}
	}
	else
	{
		//Value type
		value = std::vector<byte>(data + sizeof(TLVheader), data + sizeof(TLVheader) + length);
	}
	return true;
}

UINT32 TLV::getValueLength()
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!parent)
	{
		return static_cast<UINT32>(value.size());
	}
	UINT32 total = 0;
	std::shared_ptr<TLV> currentChild = child;
	while (currentChild.get())
	{
		total += currentChild->getTotalLength();
		currentChild = currentChild->sibling;
	}
	return total;
}

UINT32 TLV::getTotalLength()
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!parent)
	{
		return static_cast<UINT32>(value.size() + sizeof(TLVheader));
	}
	UINT32 total = 0;
	std::shared_ptr<TLV> currentChild = child;
	while (currentChild.get())
	{
		total += currentChild->getTotalLength();
		currentChild = currentChild->sibling;
	}
	return total + sizeof(TLVheader);

}

bool TLV::contains(UINT8 type)
{
	if (!parent)
		return false;
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	std::shared_ptr<TLV> currentChild = child;
	while (currentChild.get())
	{
		if (currentChild->type == type)
		{
			return true;
		}
		currentChild = currentChild->sibling;
	}
	return false;
}

UINT32 TLV::count(UINT8 type)
{
	if (!parent)
		return 0;

	UINT total = 0;
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	std::shared_ptr<TLV> currentChild = child;
	while (currentChild.get())
	{
		if (currentChild->type == type)
		{
			total++;
		}
		currentChild = currentChild->sibling;
	}
	return total;
}

std::shared_ptr<TLV> TLV::getChild(UINT8 type, UINT32 idx)
{
	if (!parent)
		return nullptr;
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	std::shared_ptr<TLV> currentChild = child;
	while (currentChild.get())
	{
		if (currentChild->type == type && !(idx--))
		{
			return currentChild;
		}
		currentChild = currentChild->sibling;
	}
	return NULL;
}

bool TLV::getAsciiStr(std::string& valueOut)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (parent)
	{
		return false;
	}
	valueOut = std::string((const char*)value.data(), value.size());
	return true;
}

#ifdef _WIN32
bool TLV::getUnicodeStr(std::wstring& valueOut)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (parent)
	{
		return false;
	}
	auto wideLength = MultiByteToWideChar(CP_UTF8, 0, reinterpret_cast<LPCCH>(value.data()), static_cast<int>(value.size()), nullptr, 0);
	valueOut = std::wstring(wideLength, L'\0');
	MultiByteToWideChar(CP_UTF8, 0, reinterpret_cast<LPCCH>(value.data()), static_cast<int>(value.size()), const_cast<LPWSTR>(valueOut.c_str()), wideLength);
	return true;
}
#endif

void TLV::addChild(std::shared_ptr<TLV> newChild)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!child.get())
	{
		child = newChild;
		return;
	}
	std::shared_ptr<TLV> currentChild = child;
	while (currentChild->sibling)
	{
		currentChild = currentChild->sibling;
	}
	currentChild->sibling = newChild;
}

std::vector<byte> TLV::genBytes()
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	std::vector<byte> result;
	if (parent)
	{
		const UINT8 parentType = type | 0x80;
		result.insert(result.end(), (byte*)&parentType, (byte*)&parentType + sizeof(parentType));
	}
	else
	{
		result.insert(result.end(), (byte*)&type, (byte*)&type + sizeof(type));
	}
	const UINT32 contentSize = this->getValueLength();
	result.insert(result.end(), (byte*)&contentSize, (byte*)&contentSize + sizeof(contentSize));
	if (!parent)
	{
		result.insert(result.end(), value.begin(), value.end());
		return result;
	}
	std::shared_ptr<TLV> currentChild = child;
	while (currentChild)
	{
		std::vector<byte> tmp = currentChild->genBytes();
		result.insert(result.end(), tmp.begin(), tmp.end());
		currentChild = currentChild->sibling;
	}
	return result;
}
