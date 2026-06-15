import React, { memo, useState, useCallback, useEffect, useRef } from "react";
import { Input } from "../ui/input";
import { Textarea } from "../ui/textarea";

// ============================================================================
// OPTIMIZED INPUT - Prevents parent re-renders during typing
// Uses local state and only syncs to parent on blur or after debounce
// ============================================================================
export const OptimizedInput = memo(({ 
  value, 
  onChange, 
  debounceMs = 300,
  syncOnBlur = true,
  ...props 
}) => {
  const [localValue, setLocalValue] = useState(value);
  const timeoutRef = useRef(null);
  
  // Sync from parent when value changes externally
  useEffect(() => {
    setLocalValue(value);
  }, [value]);
  
  const handleChange = useCallback((e) => {
    const newValue = e.target.value;
    setLocalValue(newValue);
    
    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    // Debounce the parent update
    if (debounceMs > 0) {
      timeoutRef.current = setTimeout(() => {
        onChange?.({ target: { name: props.name, value: newValue } });
      }, debounceMs);
    }
  }, [onChange, debounceMs, props.name]);
  
  const handleBlur = useCallback((e) => {
    // Clear any pending timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    // Sync immediately on blur
    if (syncOnBlur && localValue !== value) {
      onChange?.({ target: { name: props.name, value: localValue } });
    }
    
    props.onBlur?.(e);
  }, [localValue, value, onChange, syncOnBlur, props]);
  
  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);
  
  return (
    <Input 
      {...props}
      value={localValue}
      onChange={handleChange}
      onBlur={handleBlur}
    />
  );
});

OptimizedInput.displayName = "OptimizedInput";

// ============================================================================
// OPTIMIZED TEXTAREA - Same optimization for textarea
// ============================================================================
export const OptimizedTextarea = memo(({ 
  value, 
  onChange, 
  debounceMs = 300,
  syncOnBlur = true,
  ...props 
}) => {
  const [localValue, setLocalValue] = useState(value);
  const timeoutRef = useRef(null);
  
  useEffect(() => {
    setLocalValue(value);
  }, [value]);
  
  const handleChange = useCallback((e) => {
    const newValue = e.target.value;
    setLocalValue(newValue);
    
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    if (debounceMs > 0) {
      timeoutRef.current = setTimeout(() => {
        onChange?.({ target: { name: props.name, value: newValue } });
      }, debounceMs);
    }
  }, [onChange, debounceMs, props.name]);
  
  const handleBlur = useCallback((e) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    if (syncOnBlur && localValue !== value) {
      onChange?.({ target: { name: props.name, value: localValue } });
    }
    
    props.onBlur?.(e);
  }, [localValue, value, onChange, syncOnBlur, props]);
  
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);
  
  return (
    <Textarea 
      {...props}
      value={localValue}
      onChange={handleChange}
      onBlur={handleBlur}
    />
  );
});

OptimizedTextarea.displayName = "OptimizedTextarea";

export default OptimizedInput;
