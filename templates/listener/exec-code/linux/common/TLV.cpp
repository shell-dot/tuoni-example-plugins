#include"TLV.h"
#include<string>
#include <cstdint>
#include <cstring>
#include <iostream>


TLV::TLV()
{
    // An empty decode target uses the member defaults declared in TLV.h. load()
    // populates it from one host IPC envelope; callers must check that method's
    // result before accessing a value or required child.
}

TLV::TLV(UINT8 type)
{
	this->type = type;
	this->parent = true;
	this->length = 0;
}

TLV::TLV(UINT8 type, std::vector<uint8_t> data)
{
	this->type = type;
	this->parent = false;
	this->value = new UINT8[data.size()];
	memcpy(this->value, data.data(), data.size());
	this->length = data.size();
}

TLV::TLV(UINT8 type, PVOID data, UINT32 length)
{
	this->type = type;
	this->parent = false;
	this->value = new UINT8[length];
	memcpy(this->value, data, length);
	this->length = length;
}

TLV::TLV(UINT8 type, std::string data)
{
	this->type = type;
	this->parent = false;
	this->value = new char[data.length() + 1];
	memcpy(this->value, data.c_str(), data.length());
	((char*)this->value)[data.length()] = 0;
	this->length = data.length();

}

TLV::~TLV()
{
	clear();
}

bool TLV::load(std::vector<uint8_t> data)
{
	return load((PBYTE)data.data(), data.size());
}

bool TLV::load(PBYTE data, UINT32 inputLength)
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
	length = header->length;

	if (parent)
	{
		//Parent type
		PBYTE ptr = data + sizeof(TLVheader);
		std::shared_ptr<TLV> lastChild;
		UINT32 left = length;
		while (left)
		{
			std::shared_ptr<TLV> newChild(new TLV());
			if (!newChild->load(ptr, left))
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
		value = new UINT8[length];
		memcpy(value, data + sizeof(TLVheader), length);
	}
	return true;
}

UINT8 TLV::getType()
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	return type & 0x7FFFFFFF;
}

void TLV::clear()
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (value)
	{
		delete[] (PUINT8)value;
		value = NULL;
	}
	if (child)
	{
		child = NULL;
	}
}

UINT32 TLV::getValueLength()
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!parent)
	{
		return length;
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
		return length + sizeof(TLVheader);
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

bool TLV::isParent()
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	return parent;
}

bool TLV::contains(UINT8 type)
{
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
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	std::shared_ptr<TLV> currentChild = child;
	UINT32 result = 0;
	while (currentChild.get())
	{
		if (currentChild->type == type)
		{
			result++;
		}
		currentChild = currentChild->sibling;
	}
	return result;
}

std::shared_ptr<TLV> TLV::getChild(UINT8 type)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	std::shared_ptr<TLV> currentChild = child;
	while (currentChild.get())
	{
		if (currentChild->type == type)
		{
			return currentChild;
		}
		currentChild = currentChild->sibling;
	}
	return NULL;
}

std::shared_ptr<TLV> TLV::getChild(UINT8 type, UINT32 idx)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	std::shared_ptr<TLV> currentChild = child;
	while (currentChild.get())
	{
		if (currentChild->type == type)
		{
			if(idx == 0)
				return currentChild;
			idx--;
		}
		currentChild = currentChild->sibling;
	}
	return NULL;
}

std::vector<uint8_t> TLV::getValue()
{
	std::vector<uint8_t> result((uint8_t*)value, (uint8_t*)value + length);
	return result;
}

bool TLV::getUInt8(UINT8& valueOut)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!value || length != 1)
	{
		return false;
	}
	valueOut = *((PUINT8)value);
	return true;
}

bool TLV::getUInt16(UINT16& valueOut)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!value || length != 2)
	{
		return false;
	}
	valueOut = *((PUINT16)value);
	return true;
}

bool TLV::getUInt32(UINT32& valueOut)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!value || length != 4)
	{
		return false;
	}
	valueOut = *((PUINT32)value);
	return true;

}

bool TLV::getUInt64(UINT64& valueOut)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!value || length != 8)
	{
		return false;
	}
	valueOut = *((PUINT64)value);
	return true;
}

UINT8 TLV::getUInt8()
{
	UINT8 result;
	getUInt8(result);
	return result;
}

UINT16 TLV::getUInt16()
{
	UINT16 result;
	getUInt16(result);
	return result;
}

UINT32 TLV::getUInt32()
{
	UINT32 result;
	getUInt32(result);
	return result;
}

UINT64 TLV::getUInt64()
{
	UINT64 result;
	getUInt64(result);
	return result;
}

bool TLV::getStr(std::string& valueOut, UINT32& lenOut)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!value)
	{
		return false;
	}
	valueOut = std::string((const char*)value, length);
	lenOut = length;
	return true;
}

bool TLV::getStr(std::string& valueOut)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!value)
	{
		return false;
	}
	valueOut = std::string((const char*)value, length);
	return true;
}

std::string TLV::getStr()
{
	std::string result;
	getStr(result);
	return result;
}

bool TLV::getBuffer(PVOID& valueOut, UINT32& lenOut)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!value)
	{
		return false;
	}
	valueOut = new UINT8[length];
	memcpy(valueOut, value, length);
	lenOut = length;
	return true;
}

bool TLV::copyBuffer(PVOID valueOut, UINT32 lenOut)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!value || length != lenOut)
	{
		return false;
	}
	memcpy(valueOut, value, length);
	return true;
}

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

std::vector<uint8_t> TLV::genBytes()
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	std::vector<uint8_t> buffer;
	if (parent)
	{
		UINT8 parentType = type | 0x80;
		buffer.insert(buffer.end(), (uint8_t*)&parentType, (uint8_t*)&parentType + sizeof(parentType));
	}
	else
	{
		buffer.insert(buffer.end(), (uint8_t*)&type, (uint8_t*)&type + sizeof(type));
	}
	UINT32 contentSize = this->getValueLength();
	buffer.insert(buffer.end(), (uint8_t*)&contentSize, (uint8_t*)&contentSize + sizeof(contentSize));
	if (!parent)
	{
		buffer.insert(buffer.end(), (uint8_t*)value, (uint8_t*)value + length);
		return buffer;
	}
	std::shared_ptr<TLV> currentChild = child;
	while (currentChild.get())
	{
		std::vector<uint8_t> tmp = currentChild->genBytes();
		buffer.insert(buffer.end(), tmp.begin(), tmp.end());
		currentChild = currentChild->sibling;
	}
	return buffer;
}