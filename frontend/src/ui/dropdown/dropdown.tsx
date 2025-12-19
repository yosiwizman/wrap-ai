import { useState } from "react";
import { useCombobox } from "downshift";
import { cn } from "#/utils/utils";
import { DropdownOption } from "./types";
import { LoadingSpinner } from "./loading-spinner";
import { ClearButton } from "./clear-button";
import { ToggleButton } from "./toggle-button";
import { DropdownMenu } from "./dropdown-menu";
import { DropdownInput } from "./dropdown-input";

interface DropdownProps {
  options: DropdownOption[];
  emptyMessage?: string;
  clearable?: boolean;
  loading?: boolean;
  disabled?: boolean;
  placeholder?: string;
  defaultValue?: DropdownOption;
  onChange?: (item: DropdownOption | null) => void;
  testId?: string;
}

export function Dropdown({
  options,
  emptyMessage = "No options",
  clearable = false,
  loading = false,
  disabled = false,
  placeholder,
  defaultValue,
  onChange,
  testId,
}: DropdownProps) {
  const [inputValue, setInputValue] = useState(defaultValue?.label ?? "");
  const [searchTerm, setSearchTerm] = useState("");

  const filteredOptions = options.filter((option) =>
    option.label.toLowerCase().includes(searchTerm.toLowerCase()),
  );

  const {
    isOpen,
    selectedItem,
    selectItem,
    getToggleButtonProps,
    getMenuProps,
    getItemProps,
    getInputProps,
  } = useCombobox({
    items: filteredOptions,
    itemToString: (item) => item?.label ?? "",
    inputValue,
    onInputValueChange: ({ inputValue: newValue }) => {
      setInputValue(newValue ?? "");
      setSearchTerm(newValue ?? "");
    },
    defaultSelectedItem: defaultValue,
    onSelectedItemChange: ({ selectedItem: newSelectedItem }) => {
      onChange?.(newSelectedItem ?? null);
    },
    onIsOpenChange: ({
      isOpen: newIsOpen,
      selectedItem: currentSelectedItem,
    }) => {
      if (newIsOpen) {
        setSearchTerm("");
      } else {
        setInputValue(currentSelectedItem?.label ?? "");
        setSearchTerm("");
      }
    },
  });

  const isDisabled = loading || disabled;

  return (
    <div className="relative w-full" data-testid={testId}>
      <div
        className={cn(
          "bg-tertiary border border-[#717888] rounded w-full p-2",
          "flex items-center gap-2",
          isDisabled && "cursor-not-allowed opacity-60",
        )}
      >
        <DropdownInput
          placeholder={placeholder}
          isDisabled={isDisabled}
          getInputProps={getInputProps}
        />
        {loading && <LoadingSpinner />}
        {clearable && selectedItem && (
          <ClearButton onClear={() => selectItem(null)} />
        )}
        <ToggleButton
          isOpen={isOpen}
          isDisabled={isDisabled}
          getToggleButtonProps={getToggleButtonProps}
        />
      </div>
      <DropdownMenu
        isOpen={isOpen}
        filteredOptions={filteredOptions}
        selectedItem={selectedItem}
        emptyMessage={emptyMessage}
        getMenuProps={getMenuProps}
        getItemProps={getItemProps}
      />
    </div>
  );
}
