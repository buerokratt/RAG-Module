import { forwardRef, InputHTMLAttributes, PropsWithChildren, useId } from 'react';
import clsx from 'clsx';
import './FormInput.scss';
import { DefaultTFuncReturn } from 'i18next';
import { formatNumberWithCommas, removeCommasFromNumber } from 'utils/commonUtilts';

type InputProps = PropsWithChildren<InputHTMLAttributes<HTMLInputElement>> & {
  label: string;
  name: string;
  hideLabel?: boolean;
  maxLength?: number;
  error?: string;
  placeholder?: string | DefaultTFuncReturn;
  prefix?: string;
  formatAsNumber?: boolean; // New prop for number formatting
};

const FormInput = forwardRef<HTMLInputElement, InputProps>(
  (
    { label, name, disabled, hideLabel, maxLength, error, children, placeholder, prefix, formatAsNumber, onChange, value, ...rest },
    ref
  ) => {
    const id = useId();

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      let newValue = e.target.value;

      if (formatAsNumber) {
        // Remove any existing commas for processing
        const cleanValue = removeCommasFromNumber(newValue);

        // Only allow positive numbers and decimal points
        const numericValue = cleanValue.replace(/[^\d.]/g, '');

        // Prevent multiple decimal points
        const parts = numericValue.split('.');
        if (parts.length > 2) {
          newValue = parts[0] + '.' + parts.slice(1).join('');
        } else {
          newValue = numericValue;
        }

        // Format with commas
        if (newValue) {
          newValue = formatNumberWithCommas(newValue);
        }

        // Update the input value with formatted version
        e.target.value = newValue;
      }

      // Call the original onChange if provided
      if (onChange) {
        onChange(e);
      }
    };

    // Format the value prop if formatAsNumber is enabled
    const displayValue = formatAsNumber && typeof value === 'string' ? formatNumberWithCommas(value) : value;

    const inputClasses = clsx('input', disabled && 'input--disabled', error && 'input--error');

    return (
      <div className={inputClasses}>
        {label && !hideLabel && (
          <label htmlFor={id} className="input__label">
            {label}
          </label>
        )}
        <div className="input__wrapper">
          <div className="input__input-container">
            {prefix && <span className="input__prefix">{prefix}</span>}
            <input
              className={clsx('input__field', prefix && 'input__field--with-prefix', error && 'input__field--error')} name={name}
              maxLength={maxLength}
              id={id}
              ref={ref}
              aria-label={hideLabel ? label : undefined}
              value={displayValue}
              onChange={formatAsNumber ? handleInputChange : onChange}
              placeholder={placeholder}
              {...rest}
            />
          </div>
          {error && <p className="input__inline_error">{error}</p>}
          {children}
        </div>
      </div>
    );
  }
);

export default FormInput;
