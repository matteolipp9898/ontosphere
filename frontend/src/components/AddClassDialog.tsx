import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Plus } from "lucide-react";

interface AddClassDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (uri: string, label: string, description?: string) => void;
  isPending: boolean;
}

export default function AddClassDialog({
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: AddClassDialogProps) {
  const [uri, setUri] = useState("");
  const [label, setLabel] = useState("");
  const [description, setDescription] = useState("");

  const handleSubmit = () => {
    if (!uri.trim() || !label.trim()) return;
    onSubmit(uri.trim(), label.trim(), description.trim() || undefined);
    setUri("");
    setLabel("");
    setDescription("");
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      setUri("");
      setLabel("");
      setDescription("");
    }
    onOpenChange(nextOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Class</DialogTitle>
          <DialogDescription>
            Create a new class in the ontology.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <Label htmlFor="add-class-uri" className="text-xs">
              URI <span className="text-destructive">*</span>
            </Label>
            <Input
              id="add-class-uri"
              placeholder="e.g., http://example.org/MyClass"
              value={uri}
              onChange={(e) => setUri(e.target.value)}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="add-class-label" className="text-xs">
              Label <span className="text-destructive">*</span>
            </Label>
            <Input
              id="add-class-label"
              placeholder="My Class"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="add-class-desc" className="text-xs">
              Description
            </Label>
            <Textarea
              id="add-class-desc"
              placeholder="Optional description..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isPending || !uri.trim() || !label.trim()}
          >
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add Class
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
