import { rankItem } from '@tanstack/match-sorter-utils';
import { FilterFn } from '@tanstack/react-table';
import moment from 'moment';

type FormattedOption = {
  label: string;
  value: string;
};

// convert flat array to label, value pairs 
export const formattedArray = (data: string[]|undefined): FormattedOption[]|undefined => {
  return data?.map((name) => ({
    label: name?.charAt(0).toUpperCase() + name?.slice(1),
    value: name,
  }));
};

export const toLabelValueArray = <T>(
  data: T[] | undefined,
  valueField: keyof T,
  labelField: keyof T
): { label: string; value: string }[] | undefined => {
  return data?.map((item) => ({
    label: String(item[labelField]),
    value: String(item[valueField]),
  }));
};


export const convertTimestampToDateTime = (timestamp: number) => {
  return moment.unix(timestamp).format('YYYY-MM-DD HH:mm:ss');
};

// determines version numbers for filter
export const parseVersionString = (version: string) => {
  const parts = version.split('.');

  return {
    major: parts[0] !== 'x' ? parseInt(parts[0], 10) : -1,
    minor: parts[1] !== 'x' ? parseInt(parts[1], 10) : -1,
    patch: parts[2] !== 'x' ? parseInt(parts[2], 10) : -1,
  };
};

export const fuzzyFilter: FilterFn<any> = (row, columnId, value, addMeta) => {
  const itemRank = rankItem(row.getValue(columnId), value);
  addMeta({
    itemRank,
  });
  return itemRank.passed;
};

export const formatDate = (date: Date, format: string) => {
  return moment(date).format(format);
};

export const formatDateTime = (date: string) => {
  const momentDate = moment(date);
  const formattedDate = momentDate.format('DD/MM/YYYY');
  const formattedTime = momentDate.format('h.mm A');

  return {
    formattedDate,
    formattedTime,
  };
};

export const formatClassHierarchyArray = (array: string | string[]) => {
  let formattedArray: string[];
  if (typeof array === 'string') {
    try {
      const cleanedInput = array.trim();
      formattedArray = JSON.parse(cleanedInput);
    } catch (error) {
      console.error('Error parsing input string:', error);
      return '';
    }
  } else {
    formattedArray = array;
  }

  return formattedArray
    .map((item, index) =>
      index === formattedArray?.length - 1 ? item : item + ' ->'
    )
    .join(' ');
};

export const areArraysEqual = (a: string[] = [], b: string[] = []) =>
  a.length === b.length && a.every((v, i) => v === b[i]);

/**
 * Format number with comma separators (e.g., 1234567 -> "1,234,567")
 */
export const formatNumberWithCommas = (value: string | number): string => {
  // Remove any existing commas and non-numeric characters except decimal point
  const cleanValue = String(value).replace(/[^\d.]/g, '');
  
  // Split by decimal point to handle decimal numbers
  const parts = cleanValue.split('.');
  
  // Add commas to the integer part
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  
  // Join back with decimal point if it exists
  return parts.join('.');
};

/**
 * Remove commas from formatted number string (e.g., "1,234,567" -> "1234567")
 */
export const removeCommasFromNumber = (value: string): string => {
  return value.replace(/,/g, '');
};
