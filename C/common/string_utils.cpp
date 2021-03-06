/*
 * Fledge utilities functions for handling JSON document
 *
 * Copyright (c) 2018 Dianomic Systems
 *
 * Released under the Apache 2.0 Licence
 *
 * Author: Stefano Simonelli, Massimiliano Pinto
 */

#include <iostream>
#include <string>
#include "string_utils.h"

using namespace std;

/**
 * Search and replace a string
 *
 * @param out StringToManage    string in which apply the search and replacement
 * @param     StringToSearch    string to search and replace
 * @param     StringToReplace   substitution string
 *
 */
void StringReplace(std::string& StringToManage,
		   const std::string& StringToSearch,
		   const std::string& StringReplacement)
{
	if (StringToManage.find(StringToSearch) != string::npos)
	{
		StringToManage.replace(StringToManage.find(StringToSearch),
				       StringToSearch.length(),
				       StringReplacement);
	}
}

/**
 * Strips Line feed and carige return
 *
 */
void StringStripCRLF(std::string& StringToManage)
{
	string::size_type pos = 0;

	pos = StringToManage.find ('\r',pos);
	if (pos != string::npos )
	{
		StringToManage.erase ( pos, 2 );
	}

	pos = StringToManage.find ('\n',pos);
	if (pos != string::npos )
	{
		StringToManage.erase ( pos, 2 );
	}

}

/**
 * URL-encode a given string
 *
 * @param s             Input string that is to be URL-encoded
 * @return              URL-encoded output string
 */
string urlEncode(const string &s)
{
	ostringstream escaped;
	escaped.fill('0');
	escaped << hex;

	for (string::const_iterator i = s.begin(), n = s.end();
				    i != n;
				    ++i)
	{
		string::value_type c = (*i);

		// Keep alphanumeric and other accepted characters intact
		if (isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~') {
			escaped << c;
			continue;
		}

		 // Any other characters are percent-encoded
		escaped << uppercase;
		escaped << '%' << setw(2) << int((unsigned char) c);
		escaped << nouppercase;
	}

	return escaped.str();
}

/**
 * Check if a char is an hex value
 *
 * @param c	The input char
 * @return	True with hex value
 * 		false otherwise
 */
static inline bool ishex (const char c)
{
	if (isdigit(c) ||
	    c=='A' ||
	    c=='B' ||
	    c=='C' ||
	    c=='D' ||
	    c=='E' ||
	    c=='F')
	{
		return true;
	}
	else
	{
		return false;
	}
}

/**
 * URL decode of a given string
 *
 * @param name	The string to decode
 * @return	The URL decoded string
 *
 * In case of decoding errors the routine returns
 * current decoded string
 */
string urlDecode(const std::string& name)
{
	std::string decoded(name);
	char* s = (char *)name.c_str();
	char* dec = (char *)decoded.c_str();
	char* o;
	const char* end = s + name.length();
	int c;

	for (o = dec; s <= end; o++)
	{
		c = *s++;
		if (c == '+')
		{
			c = ' ';
		}
		else if (c == '%' && (!ishex(*s++) ||
			 !ishex(*s++) ||
			 !sscanf(s - 2, "%2x", &c)))
		{
			break;
		}

		if (dec)
		{
			*o = c;
		}
	}

	return string(dec);
}
