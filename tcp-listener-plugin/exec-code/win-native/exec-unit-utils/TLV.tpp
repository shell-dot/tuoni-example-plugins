#pragma once


template<typename T>
TLV::TLV(UINT8 type, T& value) : type(type), parent(false), value(reinterpret_cast<const byte*>(&value), reinterpret_cast<const byte*>(&value) + sizeof(T))
{
}

template<typename T>
TLV::TLV(UINT8 type, T&& value) : type(type), parent(false), value(reinterpret_cast<const byte*>(&value), reinterpret_cast<const byte*>(&value) + sizeof(T))
{
}

template<typename T>
bool TLV::getValue(T& valueOut)
{
	std::lock_guard<std::recursive_mutex> lk(io_mutex);
	if (!value.size() || value.size() != sizeof(T))
	{
		return false;
	}
	valueOut = *((T*)value.data());
	return true;
}
