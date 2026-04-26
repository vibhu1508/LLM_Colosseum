import { Component } from '@angular/core';

import { PromptLabComponent } from './components/prompt-lab/prompt-lab.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [PromptLabComponent],
  template: '<app-prompt-lab />',
})
export class AppComponent {}
